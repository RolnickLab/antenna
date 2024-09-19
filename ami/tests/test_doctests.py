import doctest
import pkgutil

import ami as root_package


def load_tests(loader, tests, ignore):
    modules = pkgutil.walk_packages(root_package.__path__, root_package.__name__ + ".")
    for _, module_name, _ in modules:
        try:
            suite = doctest.DocTestSuite(module_name)
        except ValueError:
            # Presumably a "no docstrings" error. That's OK.
            pass
        except ModuleNotFoundError:
            pass
        else:
            tests.addTests(suite)
    return tests
