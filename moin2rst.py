#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-
r"""
moin2rst.py [OPTIONS] [PAGENAME]

Convert a MoinMoin page to reStructuredText syntax. Example:

    moin2rst.py -u http://wiki.scipy.org/% page.txt > output.rst

Where page.txt contains the raw MoinMoin page source.  This uses a temporary
dummy wiki configuration.

If you have the full wiki and its configuration downloaded, you can do

    moin2rst.py -u http://wiki.scipy.org/% -d /path/to/wiki SomePage > out.rst

Moin versions 1.8 and 1.9 probably should work.

"""

###############################################################################
###############################################################################
# Import

import sys
import re
import os
import shutil
import tempfile
import logging

logging.disable(logging.WARNING)

from argparse import ArgumentParser
from distutils.version import LooseVersion

import MoinMoin
import MoinMoin.version
MOIN_VERSION = LooseVersion(MoinMoin.version.release)

if MOIN_VERSION >= "1.9":
    sys.path.append(os.path.join(os.path.dirname(MoinMoin.__file__),
                                 'support'))

from MoinMoin.Page import Page
from MoinMoin import wikiutil

WIKI_TEMPLATE_PATHS = ["/usr/share/moin"]

###############################################################################
###############################################################################
# Functions

def parseOptions():
    parser = ArgumentParser(usage=__doc__.rstrip().replace('%', '%%'))

    parser.add_argument("-d", "--directory", default=None, dest="directory",
                        help="Directory where the configuration of the wiki lives. "
                             "If not given, use a dummy wiki.")
    parser.add_argument("-r", "--revision", default=0, type=int, dest="revision",
                        help="Revision of the page to fetch (1-based). "
                             "Defaults to current revision.")
    parser.add_argument("-u", "--url-template", default="", dest="url_template",
                        help="If the wiki given by -d/--directory is part of a wiki "
                             "farm then this gives a template to generate an URL "
                             "from. The URL must be matched by one of the regular "
                             "expressions found in the variable 'wikis' in the "
                             "respective 'farmconfig.py'.\n"
                             "\n"
                             "'url-template' may contain at most one '%%'. The '%%' "
                             "is replaced by 'page' to form a valid URL. If '%%' is "
                             "omitted it is assumed at the end.\n"
                             "\n"
                             "Defaults to the empty string.")
    parser.add_argument('page',
                        help="The page named 'page' is used as input. Output is "
                             "to stdout.")
    args = parser.parse_args()

    percents = re.findall("%", args.url_template)
    if len(percents) == 0:
        args.url_template += "%"
    elif len(percents) > 1:
        optionParser.error("-u/--url-template must contain at most one '%'")
    if not args.revision:
        args.revision = None
    return args

###############################################################################
###############################################################################
# Now work

def get_template_path():
    for pth in WIKI_TEMPLATE_PATHS:
        fn = os.path.join(pth, "config", "wikiconfig.py")
        if os.path.exists(fn):
            return pth
    raise RuntimeError("Could not locate moinmoin config path")

def create_temp_wiki(args, pagename, destdir):
    args.directory = destdir

    # Create a template wiki
    template_path = get_template_path()
    shutil.copytree(os.path.join(template_path, "data"), 
                    os.path.join(destdir, "data"))
    shutil.copytree(os.path.join(template_path, "underlay"), 
                    os.path.join(destdir, "underlay"))

    # Copy sample config
    shutil.copyfile(os.path.join(template_path,
                                 "config",
                                 "wikiconfig.py"),
                    os.path.join(destdir, "wikiconfig.py"))

    # Copy the page over
    pagedir = os.path.join(destdir, "data", "pages", "SomePage")
    os.makedirs(os.path.join(pagedir, "revisions"))
    with open(os.path.join(pagedir, "current"), "wb") as f:
        f.write("00000001")
    shutil.copyfile(pagename, os.path.join(pagedir, "revisions", "00000001"))

    # Convert old link syntax
    pagefn = os.path.join(pagedir, "revisions", "00000001")
    with open(pagefn, 'rb') as f:
        data = f.read()

    data = re.sub(br'\[(http[^\s]+?)\s+(.+?)\]', br'[[\1|\2]]', data)
    data = re.sub(br'\["(.+?)"\]', br'[[\1]]', data)
    data = re.sub(br'\[([A-Z][a-zA-Z0-9]+)\]', br'[[\1]]', data)

    with open(pagefn, 'wb') as f:
        f.write(data)

    # Copy the plugin
    rst_plugin = os.path.join(os.path.dirname(__file__), "text_x-rst.py")
    shutil.copyfile(rst_plugin,
                    os.path.join(destdir, "data",
                                 "plugin", "formatter",
                                 "text_x-rst.py"))

def main():
    args = parseOptions()

    tmpdir = None

    cwd = os.getcwd()
    try:
        if args.directory is None:
            tmpdir = tempfile.mkdtemp()
            create_temp_wiki(args, args.page, tmpdir)
            args.page = "SomePage"

        # Needed so relative paths in configuration are found
        os.chdir(args.directory)
        # Needed to load configuration
        sys.path = [ os.getcwd(), ] + sys.path
        url = re.sub("%", re.escape(args.page), args.url_template)

        if MOIN_VERSION >= "1.9":
            from MoinMoin.web.contexts import ScriptContext as Request
        else:
            from MoinMoin.request.request_cli import Request

        class MyRequest(Request):
            def normalizePagename(self, name):
                return name
            def normalizePageURL(self, name, url):
                return args.url_template.replace('%', name)

        request = MyRequest(url=url, pagename=args.page)

        Formatter = wikiutil.importPlugin(request.cfg, "formatter",
                                          "text_x-rst", "Formatter")
        formatter = Formatter(request)
        request.formatter = formatter

        page = Page(request, args.page, rev=args.revision, formatter=formatter)
        if not page.exists():
            raise RuntimeError("No page named %r" % ( args.page, ))

        page.send_page()
    finally:
        if tmpdir is not None:
            shutil.rmtree(tmpdir)
        os.chdir(cwd)

if __name__ == '__main__':
    main()

# TODO Extension for reStructuredText parser in MoinMoin:
#
#      * Support for role `macro` for using inline macros such as
#        ``:macro:`Date(...)``` to replace the macro-as-a-link-hack
#
#      * Expansion of @SIG@ and other variables must be done by the formatter
#
#      * Role `smiley` must expand to the respective smiley
#
#      * Otherwise for standard smileys there should be a default list of
#        substitutions
#
#      * Role `icon` must expand to the respective icon
#
#      * All style roles used should be supported
#
#      * Support for "#!" literal blocks would be nice
