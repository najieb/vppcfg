#!/usr/bin/env python3
#
# Copyright (c) 2022 Pim van Pelt
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# -*- coding: utf-8 -*-
"""vppcfg is a utility to configure a running VPP Dataplane using YAML
config files. See http://github.com/pimvanpelt/vppcfg/README.md for details. """
# pylint: disable=duplicate-code
import os
import sys
import logging
import yaml

# Ensure the paths are correct when we execute from the source tree
try:
    from vppcfg.config import Validator
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from vppcfg.config import Validator
from vppcfg.vpp.reconciler import Reconciler
from vppcfg.vpp.dumper import Dumper

try:
    import argparse
except ImportError:
    print("ERROR: install argparse manually: sudo pip install argparse")
    sys.exit(-2)


def main():
    """The main vppcfg program"""
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="""enable debug logging, default False""",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="""be quiet (only warnings/errors), default False""",
    )
    parser.add_argument(
        "-f",
        "--force",
        dest="force",
        action="store_true",
        help="""force progress despite warnings, default False""",
    )

    subparsers = parser.add_subparsers(dest="command")
    check_p = subparsers.add_parser(
        "check", help="check given YAML config for validity (no VPP)"
    )
    check_p.add_argument(
        "-s",
        "--schema",
        dest="schema",
        type=str,
        help="""YAML schema validation file, default to use built-in""",
    )
    check_p.add_argument(
        "-c",
        "--config",
        dest="config",
        required=True,
        type=str,
        help="""YAML configuration file for vppcfg""",
    )

    dump_p = subparsers.add_parser(
        "dump", help="dump current running VPP configuration (VPP readonly)"
    )
    dump_p.add_argument(
        "-o",
        "--output",
        dest="outfile",
        required=False,
        default="-",
        type=str,
        help="""Output file for YAML config, default stdout""",
    )
    dump_p.add_argument(
        "-j",
        "--vpp-json-dir",
        dest="vpp_json_dir",
        required=False,
        type=str,
        help="""Directory where VPP API JSON files are located""",
    )
    dump_p.add_argument(
        "-a",
        "--vpp-api-socket",
        dest="vpp_api_socket",
        required=False,
        type=str,
        help="""Pathname of VPP API socket file""",
    )

    plan_p = subparsers.add_parser(
        "plan",
        help="plan changes from current VPP dataplane to target config (VPP readonly)",
    )
    plan_p.add_argument(
        "-s",
        "--schema",
        dest="schema",
        type=str,
        help="""YAML schema validation file, default to use built-in""",
    )
    plan_p.add_argument(
        "-c",
        "--config",
        dest="config",
        required=True,
        type=str,
        help="""YAML configuration file for vppcfg""",
    )
    plan_p.add_argument(
        "--novpp",
        dest="novpp",
        action="store_true",
        help="""Don't query VPP API, assume 'empty' dataplane config""",
    )
    plan_p.add_argument(
        "-o",
        "--output",
        dest="outfile",
        required=False,
        default="-",
        type=str,
        help="""Output file for VPP CLI commands, default stdout""",
    )
    plan_p.add_argument(
        "-j",
        "--vpp-json-dir",
        dest="vpp_json_dir",
        required=False,
        type=str,
        help="""Directory where VPP API JSON files are located""",
    )
    plan_p.add_argument(
        "-a",
        "--vpp-api-socket",
        dest="vpp_api_socket",
        required=False,
        type=str,
        help="""Pathname of VPP API socket file""",
    )

    apply_p = subparsers.add_parser(
        "apply", help="apply changes from current VPP dataplane to target config"
    )
    apply_p.add_argument(
        "-s",
        "--schema",
        dest="schema",
        type=str,
        help="""YAML schema validation file, default to use built-in""",
    )
    apply_p.add_argument(
        "-c",
        "--config",
        dest="config",
        required=True,
        type=str,
        help="""YAML configuration file for vppcfg""",
    )
    apply_p.add_argument(
        "-j",
        "--vpp-json-dir",
        dest="vpp_json_dir",
        required=False,
        type=str,
        help="""Directory where VPP API JSON files are located""",
    )
    apply_p.add_argument(
        "-a",
        "--vpp-api-socket",
        dest="vpp_api_socket",
        required=False,
        type=str,
        help="""Pathname of VPP API socket file""",
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        print("\nPlease see vppcfg <command> -h   for per-command arguments")
        sys.exit(0)

    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    if args.quiet:
        level = logging.WARNING
    logging.basicConfig(
        format="[%(levelname)-8s] %(name)s.%(funcName)s: %(message)s", level=level
    )

    opt_kwargs = {}
    if "vpp_json_dir" in args and args.vpp_json_dir is not None:
        opt_kwargs["vpp_json_dir"] = args.vpp_json_dir
    if "vpp_api_socket" in args and args.vpp_api_socket is not None:
        opt_kwargs["vpp_api_socket"] = args.vpp_api_socket

    if args.command == "dump":
        dumper = Dumper(**opt_kwargs)
        if not dumper.readconfig():
            logging.error("Could not retrieve config from VPP")
            sys.exit(-7)
        dumper.write(args.outfile)
        sys.exit(0)

    try:
        with open(args.config, "r", encoding="utf-8") as file:
            logging.info(f"Loading configfile {args.config}")
            cfg = yaml.load(file, Loader=yaml.FullLoader)
            logging.debug(f"Config: {cfg}")
    except OSError as err:
        logging.error(f"Couldn't read config from {args.config}: {err}")
        sys.exit(-1)

    validator = Validator(schema=args.schema)
    if not validator.valid_config(cfg):
        logging.error("Configuration is not valid, bailing")
        sys.exit(-2)
    logging.info("Configuration is valid")
    if args.command == "check":
        sys.exit(0)

    reconciler = Reconciler(cfg, **opt_kwargs)
    if args.novpp:
        if not reconciler.vpp.mockconfig(cfg):
            sys.exit(-7)
    else:
        if not reconciler.vpp.readconfig():
            sys.exit(-3)

        if not reconciler.phys_exist_in_vpp():
            logging.error("Not all PHYs in the config exist in VPP")
            sys.exit(-4)

        if not reconciler.phys_exist_in_config():
            logging.error("Not all PHYs in VPP exist in the config")
            sys.exit(-5)

        if not reconciler.lcps_exist_with_lcp_enabled():
            logging.error(
                "Linux Control Plane is needed, but linux-cp API is not available"
            )
            sys.exit(-6)

    failed = False
    if not reconciler.prune():
        if not args.force:
            logging.error("Planning prune failure")
            sys.exit(-10)
        failed = True
        logging.warning("Planning prune failure, continuing due to --force")

    if not reconciler.create():
        if not args.force:
            logging.error("Planning create failure")
            sys.exit(-20)
        failed = True
        logging.warning("Planning create failure, continuing due to --force")

    if not reconciler.sync():
        if not args.force:
            logging.error("Planning sync failure")
            sys.exit(-30)
        failed = True
        logging.warning("Planning sync failure, continuing due to --force")

    if args.command == "plan":
        reconciler.write(args.outfile, emit_ok=not failed)

    if failed:
        logging.error("Planning failed")
        sys.exit(-40)

    logging.info("Planning succeeded")
    if args.command == "plan":
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
