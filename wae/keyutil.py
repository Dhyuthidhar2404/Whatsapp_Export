"""The key: normalize and obtain the 64-hex E2E backup key.

``normalize`` strips only known noise (Unicode whitespace, zero-width chars,
wrapping smart-quotes) then strictly validates 64 hex chars. ``get_key`` reads
``--key-file`` or prompts with no echo. The key is never logged, printed, or
written, and never placed in :class:`~wae.context.RunContext`.

Implemented in T2.1/T2.2 (issues #5, #6).
"""
