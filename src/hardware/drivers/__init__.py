"""
OpenJ5 Concrete hardware drivers (Infrastructure layer).

Import concrete driver modules explicitly (e.g. ``hardware.drivers.a4988``) so the
GPIO backends (gpiozero/lgpio) are only needed where they are actually used.
"""
__all__: list[str] = []