from invoke import task, run
from jinja2 import Environment, FileSystemLoader
import requests

import os
import time

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
SPIDERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'documenters_aggregator/spiders')
TESTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')
FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests/files')

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


@task()
def genspider(ctx, name, domain, start_urls=None):
    """
    Make a new HTML scraping spider
    To download HTML files, use the -s flag
    and separate urls with ,
    urls cannot end in /

    Example:
    invoke genspider testspider http://www.citybureau.org -s=http://citybureau.org/articles,http://citybureau.org/staff
    """
    spider_filename = _gen_spider(name, domain)
    print('Created {0}'.format(spider_filename))

    test_filename = _gen_tests(name, domain)
    print('Created {0}'.format(test_filename))

    if start_urls:
        start_urls = start_urls.split(',http')
        if len(start_urls) > 1:
            start_urls = [start_urls[0]] + ['http{0}'.format(x) for x in start_urls[1:]]
        html_filenames = _gen_html(name, start_urls)
        for f in html_filenames:
            print('Created {0}'.format(f))

# pty is not available on Windows
try:
    import pty
    assert pty  # prevent pyflakes warning about unused import
    pty_available = True
except ImportError:
    pty_available = False


@task
def runtests(ctx):
    """
    Runs pytest, pyflakes, and pep8.
    """
    run('pytest', pty=pty_available)
    run('pyflakes .', pty=pty_available)
    run('pep8 --ignore E265,E266,E501 .', pty=pty_available)


def _make_classname(name):
    return '{0}Spider'.format(name.capitalize())


def _gen_spider(name, domain):
    filename = '{0}/{1}.py'.format(SPIDERS_DIR, name)
    with open(filename, 'w') as f:
        content = _render_content(name, domain, 'spider.tmpl')
        f.write(content)
    return filename


def _gen_tests(name, domain):
    filename = '{0}/test_{1}.py'.format(TESTS_DIR, name)
    with open(filename, 'w') as f:
        content = _render_content(name, domain, 'test.tmpl')
        f.write(content)
    return filename


def _fetch_url(url, attempt=1):
    """
    Attempt to fetch the specified url. If the request fails, retry it with an
    exponential backoff up to 5 times.
    """
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r
    except requests.exceptions.RequestException as e:
        if attempt >= 5:
            return None
        else:
            print(e)
            wait = 2 ** attempt
            print('waiting for {0} seconds'.format(wait))
            time.sleep(wait)
            return _fetch_url(url, attempt + 1)


def _gen_html(name, start_urls):
    '''urls should not end in /'''
    files = []
    for url in start_urls:
        r = _fetch_url(url)
        if r is None:
            continue

        content = r.text.strip()

        url_suffix = url.split('/')[-1]
        if '.' in url_suffix:
            url_suffix = url_suffix.split('.')[-2]
        filename = '{0}/{1}_{2}.html'.format(FILES_DIR, name, url_suffix)

        with open(filename, 'w') as f:
            f.write(content)

        files.append(filename)
    return files


def _render_content(name, domain, template):
    jinja_template = env.get_template(template)
    classname = _make_classname(name)
    return jinja_template.render(name=name, domain=domain, classname=classname)
