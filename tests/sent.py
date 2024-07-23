import random
import unittest

from dataclasses import dataclass
from typing import Callable

from bitarray import bitarray
from bitarray.util import ba2int, int2ba

from amaranth import Signal, Elaboratable, Module
from amaranth.sim import Simulator, SimulatorContext

# from ..amaranth_saej2716 import SENTReceiver


class SENTReceiver(Elaboratable):
    def __init__(self):
        self.sent_input = Signal(1)

    def elaborate(self):
        m = Module()
        return m


@dataclass
class SENTCfg:
    down_count: int = 4
    pause_count: int = 0
    random_reserved: bool = False

    def valid(self):
        return self.down_count > 4 and self.own_count < 12


CRC4_TABLE = [0, 13, 7, 10, 14, 3, 9, 4, 1, 12, 6, 11, 15, 2, 8, 5]


def crc(data):
    def loop(n: int, lookup: Callable[[int], int]) -> int:
        CheckSum16 = 5
        for offset in range(numNibbles):
            print(lookup(data, offset))
            CheckSum16 = lookup(data, offset) ^ CRC4_TABLE[CheckSum16]
        return int2ba(0 ^ CRC4_TABLE[CheckSum16], length=4)

    match data:
        case list():
            numNibbles = len(data)
            return numNibbles, lambda x, i: x[i]

        case bitarray():
            numNibbles = len(data) // 4
            assert numNibbles * 4 == len(data)
            return loop(numNibbles, lambda x, i: ba2int(x[i * 4:i * 4 + 4]))


class SENTSCNMessage:
    def __init__(self):
        self._message = None
        self._offset = 0
        pass

    @property
    def message(self):
        return self._message

    def set_message(self, _id, _byte):
        for i in _id, _byte:
            assert i >= 0 and i < 16
        self._message = bitarray()
        self._message.extend(int2ba(_id, length=4))
        self._message.extend(int2ba(_byte, length=4))
        self._message.extend(crc(self._message))
        self._offset = 0

    # TODO: Enhanced Serial Message Format
    @property
    def bit3(self) -> bool:
        if self._offset == 0 and self._message:
            return True
        else:
            return False

    @property
    def bit2(self) -> bool:
        bit = self._message[self._offset]
        self._offset += 1
        if self._offset > len(self._message):
            self._offset = 0
            self._message = None
        return bit


class SENTSender:
    def __init__(self, ctx: SimulatorContext, cfg: SENTCfg, wire: Signal):
        assert cfg.valid()
        self._ctx = ctx
        self._wire = wire
        self.cfg = cfg
        self._scn = None

    @property
    def set_scn(self, scn: SENTSCNMessage):
        self._scn = scn

    async def sent_frame_sync(self):
        await self._ctx.tick(domain="sender")
        self._ctx.set(self._wire, False)
        await self._ctx.tick(domain="sender").repeat(self._cfg.down_count)
        self._ctx.set(self._wire, True)
        await self._ctx.tick(domain="sender").repeat(56 - self._cfg.down_count)

    async def sent_nibble(self, nibble: int):
        assert nibble > 0 and nibble < 16
        self._ctx.set(self._wire, False)
        await self._ctx.tick(domain="sender").repeat(self._cfg.down_count)
        self._ctx.set(self._wire, True)
        await self._ctx.tick(domain="sender").repeat(12 + nibble)

    async def sent_scn_nibble(self):
        nibble = 0
        if self._cfg.randome_reserved:
            nibble = random.getrandbits(2)
        if self._scn:
            await self.sent_nibble(nibble & 0x3 | self._scn.bit2 >> 2 | self._scn.bit3 >> 3)
        else:
            await self.sent_nibble(nibble)

    async def sent_pause(self):
        await self._ctx.tick(domain="sender").repeat(self._cfg.pause_count)

    async def sent_message(self, message: bytearray) -> None:
        await self.sent_scn_nibble()
        async for b in message:
            self.sent_nibble(b >> 4)
            self.sent_nibble(b)
        ba = bitarray()
        ba.frombytes(message)
        await self.sent_nibble(crc(ba))
        await self.sent_pause()


class SENTTestCase(unittest.TestCase):

    def test_basic_message(self):
        dut = SENTReceiver()

        async def testbench_in(self, ctx: SimulatorContext):
            cfg = SENTCfg()
            sender = SENTSender(ctx, cfg, dut.send_in)
            msg = b'Hello'
            await sender.sent_message(msg)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_clock(3e-3, domain="sender")
        sim.add_testbench(testbench_in)
        # sim.add_testbench(testbench_out)
        with sim.write_vcd("test.vcd"):
            sim.run()
