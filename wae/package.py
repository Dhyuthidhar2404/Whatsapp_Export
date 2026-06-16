"""Bundle the export directory into the final dated ZIP.

Checks the output directory is writable with sufficient space, then zips the
export dir to ``whatsapp-export-YYYY-MM-DD.zip``, suffixing ``-2``, ``-3``, … on
same-day collision so an earlier export is never overwritten.

Implemented in T6.1 (issue #18).
"""
