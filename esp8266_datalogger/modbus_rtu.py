"""Modbus RTU for ESP8266. UART0 only (GPIO1/GPIO3 fixed, no tx=/rx=/rxbuf=)."""
import machine
import time

try:
    from log_buffer import log_print as print
except ImportError:
    pass


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


class ModbusRTU:

    def __init__(self, config):
        self.config = config
        self.uart = None
        self.de_pin = None
        self.re_pin = None
        self._init_uart()

    def _init_uart(self):
        cfg = self.config
        parity = None
        if cfg["parity"] == "E":
            parity = 0
        elif cfg["parity"] == "O":
            parity = 1
        self.uart = machine.UART(
            cfg["uart_id"],
            baudrate=cfg["baudrate"],
            bits=cfg["data_bits"],
            parity=parity,
            stop=cfg["stop_bits"],
        )
        self.uart.init(timeout=0, timeout_char=0)
        de = cfg.get("de_pin", 0)
        re = cfg.get("re_pin", 0)
        if de and de > 0:
            self.de_pin = machine.Pin(de, machine.Pin.OUT)
            self.de_pin.value(0)
        if re and re > 0:
            self.re_pin = machine.Pin(re, machine.Pin.OUT)
            self.re_pin.value(0)
        print("[RTU] UART{} {}baud {}{}{} DE={} RE={}".format(
            cfg["uart_id"], cfg["baudrate"],
            cfg["data_bits"], cfg["parity"], cfg["stop_bits"],
            de if de and de > 0 else "off",
            re if re and re > 0 else "off"))

    def _flush_rx(self):
        try:
            while self.uart.any():
                self.uart.read()
        except:
            pass

    def _expected_response_len(self, head):
        if len(head) < 2:
            return None
        func = head[1]
        if func & 0x80:
            return 5
        if func in (0x03, 0x04):
            if len(head) < 3:
                return None
            return 3 + head[2] + 2
        if func in (0x05, 0x06, 0x0F, 0x10):
            return 8
        return None

    def transceive(self, pdu, unit_id=None, quiet=True):
        if unit_id is None:
            unit_id = self.config["unit_id"]
        frame = bytes([unit_id]) + pdu
        crc = crc16_modbus(frame)
        frame += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
        self._flush_rx()
        if self.de_pin:
            self.de_pin.value(1)
        if self.re_pin:
            self.re_pin.value(1)
        self.uart.write(frame)
        tx_ms = (len(frame) * 11 * 1000) // self.config["baudrate"] + 5
        time.sleep_ms(tx_ms)
        if self.de_pin:
            self.de_pin.value(0)
        if self.re_pin:
            self.re_pin.value(0)
        deadline = time.ticks_add(time.ticks_ms(), self.config["timeout_ms"])
        response = bytearray()
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            try:
                available = self.uart.any()
            except:
                available = 0
            if available:
                chunk = self.uart.read(available)
                if chunk:
                    response.extend(chunk)
                    exp = self._expected_response_len(response[:3])
                    if exp and len(response) >= exp:
                        break
            time.sleep_ms(5)
        if len(response) < 5:
            print("[RTU] timeout ({} bytes)".format(len(response)))
            return None
        recv_crc = response[-2] | (response[-1] << 8)
        if recv_crc != crc16_modbus(response[:-2]):
            print("[RTU] CRC error")
            return None
        return response

    def forward_pdu(self, pdu, unit_id=None, quiet=True):
        response = self.transceive(pdu, unit_id, quiet)
        if not response:
            return None
        return response[1:-2]
