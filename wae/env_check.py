"""Preflight: Python version, adb availability, and device selection.

Confirms Python >= 3.9 and ``adb`` on PATH, warns below a known-good adb
version, and resolves exactly one authorized device (else raises
:class:`~wae.errors.DeviceError`). Read-only probes only.

Implemented in T1.1–T1.3 (issues #7, #8, #9).
"""
