import random
import unittest

from dataclasses import dataclass
from typing import Callable

from amaranth import Signal
from amaranth.sim import Simulator, SimulatorContext

from amaranth_saej2716 import SENTReceiver
from .bits import bitarray


class ClockModel:
    def __init__(self, ctx: SimulatorContext, period: float = 3e-4):
        self._period = period
        self._ctx = ctx

    # TODO properly model acurracy, jitter and drift
    async def tick(self, repeat: int = 1):
        await self._ctx.delay(self._period)


@dataclass
class SENTCfg:
    clock_model: ClockModel
    down_count: int = 4
    pause_count: int = 0
    random_reserved: bool = False

    def valid(self):
        return self.down_count >= 4 and self.down_count <= 12


CRC4_TABLE = [0, 13, 7, 10, 14, 3, 9, 4, 1, 12, 6, 11, 15, 2, 8, 5]


def crc(data):
    def loop(n: int, lookup: Callable[[int], int]) -> int:
        CheckSum16 = 5
        for offset in range(numNibbles):
            print(lookup(data, offset))
            CheckSum16 = lookup(data, offset) ^ CRC4_TABLE[CheckSum16]
        return (0 ^ CRC4_TABLE[CheckSum16]) & 0xf

    match data:
        case list():
            numNibbles = len(data)
            return numNibbles, lambda x, i: x[i]

        case bitarray():
            numNibbles = len(data) // 4
            assert numNibbles * 4 == len(data)
            return loop(numNibbles, lambda x, i: x[i * 4:i * 4 + 4].to_int())


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
        self._message.extend(bitarray.from_int(_id, length=4))
        self._message.extend(bitarray.from_int(_byte, length=4))
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
        self._cfg = cfg
        self._scn = None

    @property
    def set_scn(self, scn: SENTSCNMessage):
        self._scn = scn

    async def tick(self, repeat: int) -> None:
        await self._cfg.clock_model.tick(repeat)

    async def sent_frame_sync(self):
        await self.tick()
        self._ctx.set(self._wire, False)
        await self.tick(self._cfg.down_count)
        self._ctx.set(self._wire, True)
        await self.tick(56 - self._cfg.down_count)

    async def sent_nibble(self, nibble: int):
        assert nibble >= 0 and nibble < 16
        self._ctx.set(self._wire, False)
        await self.tick(self._cfg.down_count)
        self._ctx.set(self._wire, True)
        await self.tick(12 + nibble)

    async def sent_scn_nibble(self):
        nibble = 0
        if self._cfg.random_reserved:
            nibble = random.getrandbits(2)
        if self._scn:
            await self.sent_nibble(nibble & 0x3 | self._scn.bit2 >> 2 | self._scn.bit3 >> 3)
        else:
            await self.sent_nibble(nibble)

    async def sent_pause(self):
        await self.tick(self._cfg.pause_count)

    async def sent_message(self, message: bytearray) -> None:
        await self.sent_scn_nibble()
        for b in message:
            await self.sent_nibble(b >> 4)
            await self.sent_nibble(b & 0xf)
        ba = bitarray()
        ba.from_bytes(message)
        await self.sent_nibble(crc(ba))
        await self.sent_pause()


class SENTTestCase(unittest.TestCase):

    def test_basic_message(self):
        dut = SENTReceiver()

        async def testbench_in(ctx: SimulatorContext):
            cfg = SENTCfg(ctx)
            cfg.clock_model = ClockModel(ctx)
            sender = SENTSender(ctx, cfg, dut.sent_in)
            msg = b'Hello'
            await sender.sent_message(msg)

        sim = Simulator(dut)
        sim.add_clock(1e-6)
        sim.add_testbench(testbench_in)
        # sim.add_testbench(testbench_out)
        with sim.write_vcd("test.vcd"):
            sim.run()


if __name__ == '__main__':
    unittest.main()
