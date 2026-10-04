# Self-contained ASC editor test symbols

`voltage.asy` and `res.asy` were written specifically for this repository using simple generic geometry and two-pin primitive definitions. They are not copied from an LTspice installation or private coursework.

The component-edit unit test copies them beside its temporary ASC, clears the editor's symbol cache and external library search paths within the test, and uses the real PyLTSpice ASC editor. They supply parsing resources only; this test does not execute LTspice or validate simulation behavior. Production symbol lookup and the public example circuit are unchanged.
