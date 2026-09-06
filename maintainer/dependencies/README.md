# Python dependency compatibility evidence

`python-release-metadata.json` retains the exact pinned releases' primary
PyPI JSON metadata: source URL/response hash, retrieval time, Requires-Python,
Requires-Dist, and every published artifact's filename, URL and SHA-256. This
is publisher-retained evidence, not a PyPI signature or a CI execution result.

Keep one unconditional version pin per package across the declared Python
3.10–3.14 support range. A newer local interpreter must not silently raise
the minimum. `rpds-py==0.30.0` retains Python 3.10 support; the formerly pinned
2026.6.3 release excluded it. The other package pins are unchanged.

Before changing a pin, fetch its exact primary release JSON, update the
retained facts and hashes, and check the complete dependency closure. From
the pinned maintainer environment, the offline check is:

```text
python -B maintainer/scripts/python_dependency_lock.py
```

After updating the requirements and retained metadata, add `--write` to
regenerate the hash lock atomically. The tool never fetches, upgrades or
conditionally selects packages. Regression tests check every package's
Python range, transitive constraints, complete artifact hashes, and rpds
wheel availability for the supported interpreter/CI architectures.

The test attester also reads installed distribution metadata and rejects an
incompatible Requires-Python before launching the suite. This directory is
bound into both the test execution inputs and maintainer release identity.
Only actual CI execution establishes that the remote interpreter and OS
lanes passed; metadata and wheel-resolution checks cannot make that claim.
