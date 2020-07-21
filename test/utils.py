# Copyright (c) 2020 Skylark Wireless. All Rights Reserved.
import unittest
import unittest.mock

real_import = __import__
def mock_imports(import_names):
    def mock_import(name, *args):
        if name in import_names:
            return unittest.mock.MagicMock()
        else:
            return real_import(name, *args)
    return mock_import
