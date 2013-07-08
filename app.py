#!/usr/bin/env python

import os
import re
import json
import urllib2
import logging
from urllib import urlencode
from collections import defaultdict
from bottle import route, run, template, static_file, request, redirect, default_app

import config

logging.basicConfig(format = '%(asctime)-15s %(message)s', level = logging.DEBUG)

diamond_re = re.compile('^servers\.(?P<server>[^\.]+)\.(?P<plugin>[^\.]+)\..*$')
bad_metric = [
    re.compile('^servers\.[^\.]+\.memory\.Vmalloc.*$'),
]
diamond = None


if os.path.exists(config.metrics_file):
    metrics = json.loads(open(config.metrics_file).read())
else:
    data = urllib2.urlopen(config.graphite_url + '/metrics/index.json').read()
    try:
        open(config.metrics_file, 'w').write(data)
    except:
        logging.warning('dumps %s error' % config.metrics_file)
        pass
    metrics = json.loads(data)

def is_bad_metric(metric):
    global bad_metric
    for r in bad_metric:
        if r.match(metric):
            return True

def find_metrics(search):
    global metrics
    matched_metrics = []
    try:
        re_obj = re.compile(search)
    except:
        return None
    for m in metrics:
        if re_obj.search(m):
            matched_metrics.append(m)
    return matched_metrics

def find_metrics_of_plugin_by_server_regex(plugin, server_regex):
    global diamond
    data = {}
    re_obj = re.compile(server_regex)
    for s in diamond.keys():
        if re_obj.match(s):
            if diamond[s].has_key(plugin):
                data[s] = diamond[s][plugin]
    return data


def get_diamond():
    global metrics
    diamond = {}
    for m in metrics:
        if is_bad_metric(m):
            continue
        o = diamond_re.match(m)
        if o:
            d = o.groupdict()
            if not diamond.has_key(d['server']):
                diamond[d['server']] = {}
            if not diamond[d['server']].has_key(d['plugin']):
                diamond[d['server']][d['plugin']] = []
            diamond[d['server']][d['plugin']].append(m)
    return diamond

diamond = get_diamond()



def render_page(body, **kwargs):
    return str(template('templates/base', body = body, **kwargs))

@route('/', method = 'GET')
@route('/', method = 'POST')
@route('/index', method = 'GET')
@route('/index', method = 'POST')
def index():
    global diamond
    if request.method == 'POST':
        search = request.forms.get('search', '')
        if search.strip():
            return redirect('/regex/?' + urlencode({'search':search}))
    body = template('templates/index', diamond = diamond)
    return render_page(body)

@route('/dashboard', method = 'GET')
def dashboard():
    global diamond
    plugins = defaultdict(dict)
    for s in diamond.keys():
        prefix  = re.sub('\d+$', '', s)
        for p in diamond[s].keys():
            plugins[p][prefix] = True # dict is faster than set
    body = template('templates/dashboard', **locals())
    return render_page(body, page = 'dashboard')

@route('/server/<server>', method = 'GET')
def server(server = ''):
    global diamond
    data = diamond[server]
    body = template('templates/server', **locals())
    return render_page(body)

@route('/server/<server>/<plugin>', method = 'GET')
def plugin(server = '', plugin = ''):
    global diamond
    data = diamond[server][plugin]
    body = template('templates/plugin', **locals())
    return render_page(body)

@route('/metric/<metric_name>', method = 'GET')
def metric(metric_name = ''):
    body = template('templates/metric', m = metric_name)
    return render_page(body)

@route('/regex/', method = 'GET')
def regex():
    search = request.query.get('search', '')
    if ':' in search:
        plugin, server_regex = search.strip().split(':')
        data = find_metrics_of_plugin_by_server_regex(plugin, server_regex)
        body = template('templates/plugin-regex', **locals())
    else:
        matched_metrics = find_metrics(search)
        body = template('templates/graph', **locals())
    return render_page(body, search = search)

@route('<path:re:/static/css/.*css>')
@route('<path:re:/static/js/.*js>')
def static(path, method = 'GET'):
    return static_file(path, root = '.')


