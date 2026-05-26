"""OPC Team tooling package.

The submodules use bare imports (e.g. ``from config import get_config``).
``cli.main`` adds this directory to ``sys.path`` before dispatching so the
modules can also be imported flat from the source tree.
"""
