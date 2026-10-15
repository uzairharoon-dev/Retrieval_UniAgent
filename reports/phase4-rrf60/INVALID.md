This run is superseded and must not be used to assess fusion effectiveness.
Both tokenizer limits were changed inside one Java process; the long component
behaved like the short component. The integration test was strengthened to
require different component rankings on a discriminating fixture, and the
system now runs each component in a fresh process.

The corrected experiment is `phase4-rrf60-isolated`. Original artifacts are
retained for debugging, not presented as valid 20/64 fusion results.
