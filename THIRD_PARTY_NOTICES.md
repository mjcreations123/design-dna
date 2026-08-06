# Third-party notices

The Design DNA runtime does not vendor third-party libraries, fonts, images,
templates, or browser binaries.

Maintainer development uses the version-pinned Python package set in
`maintainer/requirements-dev.txt` and the cross-platform SHA-256 artifact lock
in `maintainer/requirements-dev.lock`. Rendered-browser verification uses the
version-pinned Playwright dependency and integrity-locked transitive closure in
`maintainer/package-lock.json`. Browser binaries and installed dependency
directories are not redistributed in this source package.

Each dependency remains governed by its upstream license. Before distributing a
binary bundle or hosted service, generate a dependency inventory from the exact
release environment, retain upstream license texts as required, and have the
result reviewed for the intended distribution model.

Public research references remain citations, not bundled copies or a grant to
republish the underlying material.
