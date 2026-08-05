import unittest
from pathlib import Path

from stickos.image import build_from_rom, build_image
from stickos.say_compile import compile_say
from stickos.vm import StickImage, StickVM

PKG = Path(__file__).resolve().parents[1]  # stickos/


class TestSay(unittest.TestCase):
    def test_compile_push_say(self):
        c = compile_say('put 42\nsay\nhalt\n')
        self.assertGreater(len(c.code), 0)
        img = build_image('put 42\nsay\nhalt\n')
        r = StickVM(img).run()
        self.assertTrue(r.ok)
        self.assertIn("42", r.output)

    def test_native_is_kilobytes(self):
        img, blob = build_from_rom(PKG / "rom")
        self.assertLessEqual(len(blob), 8 * 1024)
        self.assertGreater(len(blob), 32)
        self.assertEqual(blob[:4], b"STK1")

    def test_roundtrip(self):
        _, blob = build_from_rom(PKG / "rom")
        img = StickImage.from_bytes(blob)
        r = StickVM(img).run()
        self.assertTrue(r.ok)
        self.assertTrue(any("PASS" in line for line in r.output))

    def test_product_demo(self):
        src = (PKG / "demos" / "product.say").read_text()
        r = StickVM(build_image(src)).run()
        self.assertTrue(r.ok)
        self.assertIn("120", r.output)


class TestIndependence(unittest.TestCase):
    def test_bench_imports_are_power_only(self):
        from stickos.bench.independence import audit_bench_source

        self.assertEqual(audit_bench_source(), [])

    def test_vbus_only_boot(self):
        from stickos.bench.independence import assert_uart_autonomous
        from stickos.bench.power import UsbPowerBench
        from stickos.silicon.build_fw import build

        fw = build()
        log = UsbPowerBench(firmware=fw).apply_vbus()
        self.assertEqual(log.exit_code, 0)
        self.assertEqual(assert_uart_autonomous(log.uart_lines), [])
        joined = "\n".join(log.uart_lines)
        self.assertIn("runall:", joined)
        self.assertIn("adapt: mode=1", joined)
        self.assertIn("adapt: mode=2", joined)


class TestUniversal(unittest.TestCase):
    def test_runall_executes_rom_apps(self):
        from stickos.image import build_from_rom

        img, _ = build_from_rom(PKG / "rom")
        r = StickVM(img).run(max_ticks=500_000)
        self.assertTrue(r.ok)
        joined = "\n".join(r.output)
        self.assertIn("--- app:hello.app ---", joined)
        self.assertIn("APP hello-world", joined)
        self.assertIn("StickOS ready — adapted.", joined)


if __name__ == "__main__":
    unittest.main()
