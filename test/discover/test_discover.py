#!/usr/bin/env python3
# Copyright (c) 2020 Skylark Wireless. All Rights Reserved.
import copy
import unittest.mock
import os
import site
import json
import yaml

filepath = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.join(filepath, '..', '..'))

from test.utils import mock_imports

with unittest.mock.patch('builtins.__import__', side_effect=mock_imports(["SoapySDR", ])):
    from pyfaros.discover import discover

@unittest.mock.patch("time.sleep", autospec=True)
class TestDiscover(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None

    def convert_discover_to_dict(self, devices):
        retval = {
            "hubs": [],
            "iris": [],
            "cpe": [],
            "vger": [],
        }
        for hub in devices._hubs:
            hub_data = {
                "serial": hub.serial,
                "chains": {},
            }
            if hub.error:
                hub_data["error"] = True
            retval["hubs"].append(hub_data)
            for (chidx, irises) in [(k, hub.chains[k]) for k in sorted(hub.chains.keys())]:
                rrh_data = {
                    "nodes": {}
                }
                hub_data["chains"][str(chidx+1)] = rrh_data
                if isinstance(irises, discover.RRH) and irises.serial:
                    rrh_data["serial"] = irises.serial
                    for iris in irises:
                        node_index = str(iris.rrh_index+1)
                        if node_index in rrh_data["nodes"]:
                            if type(rrh_data["nodes"][node_index]) != list:
                                rrh_data["nodes"][node_index] = [rrh_data["nodes"][node_index], ]
                            rrh_data["nodes"][node_index].append(iris.serial)
                        else:
                            rrh_data["nodes"][node_index] = iris.serial
                else:
                    for rrh_index, iris in irises.items():
                        rrh_data["nodes"][str(rrh_index+1)] = iris.serial
                if irises.error:
                    rrh_data["error"] = True

        if devices._standalone_irises:
            for node in devices._standalone_irises:
                retval["iris"].append(node.serial)

        if devices._cpes:
            for node in devices._standalone_irises:
                retval["cpe"].append(node.serial)

        if devices._vgers:
            for node in devices._vgers:
                retval["vger"].append(node.serial)

        return retval

    class Device(object):
        def __init__(self, devices):
            self._devices = devices
        def enumerate(self, _):
            return self._devices

    def run_with_config(self, test_config):
        async def mock_afetch(dev):
            dev._json = test_config["status"].get(dev.serial, {})
            return dev

        with unittest.mock.patch.object(discover.SoapySDR, "Device",
                                        self.Device(test_config["enumerate"])) as SoapyDevice, \
             unittest.mock.patch.object(discover.Remote, "afetch", mock_afetch), \
             unittest.mock.patch.object(discover.HubRemote, "_update_irises", autospec=True, return_value=None):
            devices = discover.Discover()
        print()
        print(devices)
        output = self.convert_discover_to_dict(devices)
        print(json.dumps(output, indent=4))
        self.assertDictEqual(test_config["expected_devices"], output)
        if "as_yaml" in test_config:
            as_yaml = devices._as_yaml()
            print("yaml:\n{}".format(as_yaml))
            expected = '\n'.join(test_config["as_yaml"])
            self.assertEqual(
                yaml.load(expected, Loader=yaml.FullLoader),
                yaml.load(as_yaml, Loader=yaml.FullLoader))

        return devices

    def test_discover(self, _):
        with open(os.path.join(filepath, "test_discover.json"), "r") as fptr:
            test_config = json.load(fptr)
        devices = self.run_with_config(test_config)

    def test_partial_discover(self, _):
        with open(os.path.join(filepath, "test_partial_discover.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)

    def test_discover_chain_5(self, _):
        with open(os.path.join(filepath, "test_discover_chain_5.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)

    def test_discover_with_bad_rrh_index(self, _):
        # Reproduce https://gitlab.com/skylark-wireless/software/sklk-dev/-/issues/191
        with open(os.path.join(filepath, "test_discover_chain_5.json"), "r") as fptr:
            test_config = json.load(fptr)
        # Modify the chain output to reproduce a sklk-dev bug where the chain and message indexes are wrong
        for node in test_config["status"].values():
            if "message_index" in node["global"].keys():
                node["global"]["message_index"] -= 1
                node["global"]["chain_index"] = 0
        hub_0 = test_config["expected_devices"]["hubs"][0]
        hub_0["chains"]["8"] = hub_0["chains"].pop("5")
        hub_0["chains"]["8"]["error"] = True
        hub_0["error"] = True
        self.run_with_config(test_config)

    def test_discover_with_no_hub(self, _):
        # Reproduce https://gitlab.com/skylark-wireless/software/sklk-dev/-/issues/191
        with open(os.path.join(filepath, "test_discover_chain_5.json"), "r") as fptr:
            test_config = json.load(fptr)
        # Modify the chain output to reproduce a sklk-dev bug where the chain and message indexes are wrong
        test_config["enumerate"] = [node for node in test_config["enumerate"] if node["serial"] != "FH4A000005"]
        test_config["expected_devices"]["iris"] = \
            list(test_config["expected_devices"]["hubs"][0]["chains"]["5"]["nodes"].values())
        del test_config["expected_devices"]["hubs"][0]
        self.run_with_config(test_config)

    def test_discover_with_no_head(self, _):
        # Reproduce https://gitlab.com/skylark-wireless/software/sklk-dev/-/issues/191
        with open(os.path.join(filepath, "test_discover_chain_5.json"), "r") as fptr:
            test_config = json.load(fptr)
        # Modify the chain output to reproduce a sklk-dev bug where the chain and message indexes are wrong
        test_config["enumerate"] = [node for node in test_config["enumerate"] if node["serial"] != "RF3E000336"]
        hub_0 = test_config["expected_devices"]["hubs"][0]
        del hub_0["chains"]["5"]["nodes"]["1"]
        del hub_0["chains"]["5"]["serial"]
        # REVISIT: Behavior has been modified to list as unknown instead of trusting the chain number
        hub_0["chains"]["8"] = hub_0["chains"].pop("5")
        hub_0["chains"]["8"]["error"] = True
        hub_0["error"] = True
        self.run_with_config(test_config)

    def test_discover_double_chain(self, _):
        with open(os.path.join(filepath, "pyfaros-discover-2020-06-24_15:00:14.430310.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)

    def test_discover_2020_06_incompatible(self, _):
        with open(os.path.join(filepath, "discover-2020-06-incompatible.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)
