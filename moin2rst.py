#! /usr/bin/env python
# -*- coding: iso-8859-1 -*-

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

from optparse import OptionParser, OptionGroup
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
    """
    Sets options and returns arguments.

    @return: Name of the input page.
    @rtype: ( str, )
    """
    optionParser = OptionParser(usage="usage: %prog [option]... <page>",
                                description="""Convert a MoinMoin page to reStructuredText syntax.""")

    generalGroup = OptionGroup(optionParser, "General options")
    generalGroup.add_option("-d", "--directory",
                            default=None, dest="directory",
                            help="""Directory where the configuration of the wiki lives.

If not given, use a dummy wiki.""")
    generalGroup.add_option("-r", "--revision",
                            default=0, type=int, dest="revision",
                            help="""Revision of the page to fetch (1-based).

Defaults to current revision.""")
    generalGroup.add_option("-u", "--url-template",
                            default="", dest="url_template",
                            help="""If the wiki given by -d/--directory is part of a wiki farm then this gives a
template to generate an URL from. The URL must be matched by one of the regular
expressions found in the variable "wikis" in the respective "farmconfig.py".

"url-template" may contain at most one '%'. The '%' is replaced by "page"
to form a valid URL. If '%' is omitted it is assumed at the end.

Defaults to the empty string.""")
    optionParser.add_option_group(generalGroup)

    argumentGroup = OptionGroup(optionParser, "Arguments")
    optionParser.add_option_group(argumentGroup)
    argument1Group = OptionGroup(optionParser, "page", """The page named "page" is used as input. Output is to stdout.""")
    optionParser.add_option_group(argument1Group)

    options, args = optionParser.parse_args()

    if len(args) != 1:
        optionParser.error("Exactly one argument required")

    percents = re.findall("%", options.url_template)
    if len(percents) == 0:
        options.url_template += "%"
    elif len(percents) > 1:
        optionParser.error("-u/--url-template must contain at most one '%'")
    if not options.revision:
        options.revision = None

    return options, args[0]

###############################################################################
###############################################################################
# Now work

def get_template_path():
    for pth in WIKI_TEMPLATE_PATHS:
        fn = os.path.join(pth, "config", "wikiconfig.py")
        if os.path.exists(fn):
            return pth
    raise RuntimeError("Could not locate moinmoin config path")

def create_temp_wiki(options, pagename, destdir):
    options.directory = destdir

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

    data = re.sub(br'\[(http.+?)\s+(.+?)\]', br'[[\1|\2]]', data)
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
    options, pageName = parseOptions()

    tmpdir = None

    cwd = os.getcwd()
    try:
        if options.directory is None:
            tmpdir = tempfile.mkdtemp()
            create_temp_wiki(options, pageName, tmpdir)
            pageName = "SomePage"

        # Needed so relative paths in configuration are found
        os.chdir(options.directory)
        # Needed to load configuration
        sys.path = [ os.getcwd(), ] + sys.path
        url = re.sub("%", re.escape(pageName), options.url_template)

        if MOIN_VERSION >= "1.9":
            from MoinMoin.web.contexts import ScriptContext
            class Request(ScriptContext):
                def normalizePagename(self, name):
                    return name
        else:
            from MoinMoin.request.request_cli import Request

        request = Request(url=url, pagename=pageName)

        Formatter = wikiutil.importPlugin(request.cfg, "formatter",
                                          "text_x-rst", "Formatter")
        formatter = Formatter(request)
        request.formatter = formatter

        page = Page(request, pageName, rev=options.revision, formatter=formatter)
        if not page.exists():
            raise RuntimeError("No page named %r" % ( pageName, ))

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
