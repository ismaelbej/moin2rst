"""
    MoinMoin - Render as reStructuredText action - redirects to the reStructuredText formatter

    @copyright: 2008 Stefan Merten
    @license: GNU GPL, see COPYING for details.
"""
# Modified for MoinMoin Version 1.9 by IanRiley 2012-01-04

from MoinMoin.Page import Page

def execute(pagename, request):
    url = Page(request, pagename).url(request, {'action': 'format', 'mimetype': 'text/x-rst'})
    return request.http_redirect(url)

