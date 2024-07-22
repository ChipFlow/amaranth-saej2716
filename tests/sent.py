import random
from dataclasses import dataclass
from typing import Callable

from bitarray import bitarray
from bitarray.util import ba2int, int2ba

from amaranth import Signal, Elaboratable, Module
from amaranth.sim import SimulatorContext


class SENDReceiver(Elaboratable):
    def __init__(self):
        self.s = Signal(1)

    def elaborate(self):
        m = Module()
        return m


@dataclass
class SENDCfg:
    down_count: int = 4
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


class SENDSCNMessage:
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


async def simulate_sent(ctx: SimulatorContext, wire: Signal, cfg: SENDCfg, scn: SENDSCNMessage):
    assert cfg.valid()

    async def sent_frame_sync():
        await ctx.tick()
        ctx.set(wire, False)
        await ctx.tick().repeat(cfg.down_count)
        ctx.set(wire, True)
        await ctx.tick().repeat(56 - cfg.down_count)

    async def sent_nibble(nibble: int):
        assert nibble > 0 and nibble < 16
        ctx.set(wire, False)
        await ctx.tick().repeat(cfg.down_count)
        ctx.set(wire, True)
        await ctx.tick().repeat(12 + nibble)

    async def sent_scn_nibble():
        nibble = 0
        if cfg.randome_reserved:
            nibble = random.getrandbits(2)
        await sent_nibble(nibble & 0x3 | scn.bit2 >> 2 | scn.bit3 >> 3)

    async def sent_message(message: bytearray, pause: int = 0) -> None:
        sent_scn_nibble(scn)
        async for b in message:
            sent_nibble(b >> 4)
            sent_nibble(b)
        ba = bitarray()
        ba.frombytes(message)
        sent_nibble(crc(ba))


def main():
    m = SENDSCNMessage()
    m.set_message(0x3, 0xB)


if __name__ == "__main__":
    main()
