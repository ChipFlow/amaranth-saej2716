from enum import Enum, auto

from amaranth import Module, Print
from amaranth.lib.wiring import Component, In, Out, Signature,  Struct, StructLayout, UnionLayout
from amaranth_soc import csr


class SENTFrame(Struct):
    """
.. list-table:: SEND Frame formats!
      :header-rows: 1

    * - Frame Format
      - Data Nibbles
      - Data 1
      - Data 2
      - Data 3
      - Data 4
      - Data 5
      - Data 6
    * - H.1 Two 12-bit fast channels
      - 6
      - Ch1 MSN
      - Ch1 MidN
      - Ch1 LSN
      - Ch2 LSN
      - Ch2 MidN
      - Ch2 MSN
    * - H.2 One 12-bit fast channel
      - 3
      - Ch1 MSN
      - Ch1 MidN
      - Ch1 LSN
      - Not implemented
      - Not implemented
      - Not implemented
    * - H.3 High-speed with one 12-bit fast channel
      - 4
      - Most significant bits 11 - 9
      - Bits 8 – 6
      - Bits 5 – 3
      - Least significant bits 2 - 0
      - Not implemented
      - Not implemented
    * - H.4 Secure sensor with 12-bit fast channel 1 and secure sensor information on fast channel 2
      - 6
      - Ch1 MSN
      - Ch1 MidN
      - Ch1 LSN
      - Counter MSN
      - Counter LSN
      - Inverted Copy Ch1 MSN
    * - H.5 Single sensor with 12-bit fast channel 1 and zero value on fast channel 2
      - 6
      - Ch1 MSN
      - Ch1 MidN
      - Ch1 LSN
      - Zero
      - Zero
      - Zero
    * - H.6: Two fast channels with 14-bit fast channel 1 and 10-bit fast channel 2
      - 6
      - Ch1 MSN
      - Ch1 MidMSN
      - Ch1 MidLSN
      - Ch1/Ch2 LSN
      - Ch2 MidN
      - Ch2 MSN
    * - H.7: Two fast channels with 16-bit fast channel 1 and 8-bit fast channel 2
      - 6
      - Ch1 MSN
      - Ch1 MidMSN
      - Ch1 MidLSN
      - Ch1 LSN
      - Ch2 LSN
      - Ch2 MSN
    """

    class Format(Enum):
        H1 = auto()
        H2 = auto()
        H3 = auto()
        H4 = auto()
        H5 = auto()
        H6 = auto()
        H7 = auto()

    valid: 1
    fmt: Format
    channels: UnionLayout({
        "h1": StructLayout({
            "ch1": Out(12),
            "ch2": Out(12)
        }),
        "h2": StructLayout({
            "ch1": Out(12)
        }),
        "h3": StructLayout({
            "ch1": Out(12)
        }),
        "h4": StructLayout({
            "ch1": Out(12),
            "ch2": Out(8)
        }),
        "h5": StructLayout({
            "ch1": Out(12)
        }),
        "h6": StructLayout({
            "ch1": Out(14),
            "ch2": Out(10)
        }),
        "h7": StructLayout({
            "ch1": Out(14),
            "ch2": Out(10)
        })
    })


class SENTReceiver(Component):

    sent_in: In(1)
    frames: Out(SENTFrame)

    class Config(csr.Register, access="w"):
        """
        reset: reset the core, e.g. in case of a bus lockup
        frame_size:
        stop: write 1 to trigger I2C stop
        read_ack: write 1 to trigger I2C read and ACK
        read_nack: write 1 to trigger I2C read and NACK
        """
        reset: csr.Field(csr.action.W, unsigned(1))
        start: csr.Field(csr.action.W, unsigned(1))
        stop: csr.Field(csr.action.W, unsigned(1))
        read_ack: csr.Field(csr.action.W, unsigned(1))
        read_nack: csr.Field(csr.action.W, unsigned(1))


    def elaborate(self, platform):
        m = Module()
        m.d.sync += Print("on tick: ", self.sent_in)
        return m
