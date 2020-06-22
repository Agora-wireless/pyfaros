#!/usr/bin/env python3
import copy
import unittest.mock
import os
import site
import SoapySDR
import urllib.request
import json
import http.client
from argparse import Namespace
from elasticsearch import Elasticsearch
import logging
import time
from pprint import pprint

filepath = os.path.dirname(os.path.abspath(__file__))
site.addsitedir(os.path.join(filepath, '..', '..'))

from pyfaros.discover import discover

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
            retval["hubs"].append(hub_data)
            for (chidx, irises) in [(k, hub.chains[k]) for k in sorted(hub.chains.keys())]:
                rrh_data = {
                    "nodes": {}
                }
                hub_data["chains"][str(chidx+1)] = rrh_data
                if isinstance(irises, discover.RRH) and irises.serial:
                    rrh_data["serial"] = irises.serial
                    for iris in irises:
                        rrh_data["nodes"][str(iris.rrh_index+1)] = iris.serial
                else:
                    for rrh_index, iris in irises.items():
                        rrh_data["nodes"][str(rrh_index+1)] = iris.serial

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

    def run_with_config(self, test_config):
        async def mock_afetch(dev):
            dev._json = test_config["status"].get(dev.serial, {})
            return dev

        with unittest.mock.patch.object(SoapySDR.Device, "enumerate", autospec=True, return_value=test_config["enumerate"]), \
             unittest.mock.patch.object(discover.Remote, "afetch", mock_afetch):
            devices = discover.Discover()
        output = self.convert_discover_to_dict(devices)
        self.assertDictEqual(test_config["expected_devices"], output)
        return devices

    @unittest.mock.patch("time.sleep", autospec=True)
    def test_discover(self, _):
        with open(os.path.join(filepath, "test_discover.json"), "r") as fptr:
            test_config = json.load(fptr)
        devices = self.run_with_config(test_config)

    @unittest.mock.patch("time.sleep", autospec=True)
    def test_partial_discover(self, _):
        with open(os.path.join(filepath, "test_partial_discover.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)

    @unittest.mock.patch("time.sleep", autospec=True)
    def test_discover_chain_5(self, _):
        with open(os.path.join(filepath, "test_discover_chain_5.json"), "r") as fptr:
            test_config = json.load(fptr)
        self.run_with_config(test_config)

    @unittest.mock.patch("time.sleep", autospec=True)
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
        self.run_with_config(test_config)
