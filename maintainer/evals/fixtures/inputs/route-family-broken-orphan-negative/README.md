# Broken declaration and orphan route — negative fixture

This source-frozen fictional project declares `/missing/`, which has no
document, and contains `/orphan/`, which is absent from the declaration and
unreachable from the supplied pages.

The visible link between the two valid declared pages is intact so package-wide
link checks remain meaningful. The route-family audit must still report the
missing declared route, the orphan document, and the route-count mismatch.
Do not edit supplied files.
