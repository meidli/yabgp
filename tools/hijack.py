#!/usr/bin/env python
# -*- coding:utf-8 -*-

# Copyright 2015 Cisco Systems, Inc.
# All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

""" BGP Route injector
"""

from __future__ import print_function
import sys
import urllib2
import json
import time

from oslo_config import cfg
import random

CONF = cfg.CONF

CONF.register_cli_opts([
    cfg.StrOpt('peerip', help='The BGP peer address'),
    cfg.IntOpt('interval',default=0, help='time interval when sending message')]
)

rest_server_ops = [
    cfg.StrOpt('host',
               default='0.0.0.0',
               help='Address to bind the API server to'),
    cfg.IntOpt('port',
               default=8801,
               help='Port the bind the API server to'),
    cfg.StrOpt('user',
               default='admin',
               help='Username for api server'),
    cfg.StrOpt('passwd',
               default='admin',
               help='Password for api server',
               secret=True)
]

CONF.register_cli_opts(rest_server_ops, group='rest')


msg_source_ops = [
    cfg.StrOpt('json',
               help='json format update messages'),
    cfg.StrOpt('list',
               help='yabgp raw message file')
]

CONF.register_cli_opts(msg_source_ops, group='message')

bgp_config_ops = [
    cfg.StrOpt('nexthop',
               help='new next hop address'),
    cfg.StrOpt('originator_id',
               help='new originator id'),
    cfg.ListOpt('cluster_list',
                help='new cluster list'
                ),
    cfg.BoolOpt('no_origin_cluster',
                default=True,
                help='remove originator id and cluster list'),
    cfg.BoolOpt('hijack',
                default=True,
                help='hijack'),
    cfg.IntOpt('num',default=10,
               help='new next hop address'),
]

CONF.register_cli_opts(bgp_config_ops, group='attribute')


URL = 'http://%s:%s/v1/peer/%s/send/update'


def get_api_opener_v1(url, username, password):
    """
    get the http api opener with base url and username,password

    :param url: http url
    :param username: username for api auth
    :param password: password for api auth
    """
    # create a password manager
    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()

    # Add the username and password.
    password_mgr.add_password(None, url, username, password)

    handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(handler)
    return opener


def get_data_from_agent(url, username, password, method='GET', data=None):
    """
    HTTP interaction with yabgp rest api
    :param url:
    :param username:
    :param password:
    :param method:
    :param data:
    :return:
    :return:
    """
    # build request
    if data:
        data = json.dumps(data)
    request = urllib2.Request(url, data)
    request.add_header("Content-Type", 'application/json')
    request.get_method = lambda: method
    opener_v1 = get_api_opener_v1(url, username, password)
    try:
        res = json.loads(opener_v1.open(request).read())
        return True
    except Exception:
        return False


def interval():
    time.sleep(CONF.interval)


def linecount():
    count = 0
    with open(CONF.message.json) as f:
        for line in f.xreadlines():
            count += 1
    return count


def send_update():
    # get the message count
    message_count = float(linecount())
    url = 'http://{bind_host}:{bind_port}/v1/peer/{peer_ip}/send/update'
    url = url.format(bind_host=CONF.rest.host, bind_port=CONF.rest.port, peer_ip=CONF.peerip)
    bar_length = 50
    message_pass_send = 0
    send_success = 0
    send_failed = 0
    current_percent = 0.00
    percent_step = 0.01
    with open(CONF.message.json) as f:
        # sys.stdout.write("\rPercent: [%s] %.2f%%" % ('' + ' ' * bar_length, current_percent))
        current_percent += percent_step
        sys.stdout.flush()

        start_number = random.randint(1000, 100000)

        for _message in f.xreadlines():
            message_json = json.loads(_message)
            if message_json['type'] != 2:
                message_count -= 1
                continue

            if message_count>= start_number and message_count < start_number+ 100:

                message = message_json['msg']

                if message['attr']:
                    print(message_count)
                    flag = random.randint(0,1)
                    as_path = message['attr']['2'][0][1]
                    # orgin_as not change
                    if flag == 1:
                        orgin_as = as_path[-1]
                        new_as_path = []
                        for item in range(len(as_path) -1):
                            new_as_path.append(random.randint(1, 65535))
                        new_as_path.append(orgin_as)
                    else:
                        new_as_path = as_path[:-1]
                        new_as_path.append(random.randint(1, 65535))
                    print(message_count, as_path, new_as_path)
                    message['attr']['2'][0][1] = new_as_path

                if message['nlri']:
                    if CONF.attribute.no_origin_cluster:
                        if message['attr'].get('9'):
                            message['attr'].pop('9')
                        if message['attr'].get('10'):
                            message['attr'].pop('10')
                    elif CONF.attribute.originator_id and CONF.attribute.cluster_list:
                        message['attr']['9'] = CONF.attribute.originator_id
                        message['attr']['10'] = CONF.attribute.cluster_list
                    if CONF.attribute.nexthop:
                        message['attr']['3'] = CONF.attribute.nexthop
                    post_data = {
                        'nlri': message['nlri'],
                        'attr': message['attr']
                    }
                    print(post_data)
                    res = get_data_from_agent(url, 'admin', 'admin', 'POST', post_data)
                    if res:
                        send_success += 1
                        interval()
                    else:
                        send_failed += 1
                    while message_pass_send/1000 >= current_percent/100:
                        hashes = '#' * int(message_pass_send/1000 * bar_length)
                        spaces = ' ' * (bar_length - len(hashes))
                        # sys.stdout.write("\rPercent: [%s] %.2f%%" % (hashes + spaces, current_percent))
                        sys.stdout.flush()
                        current_percent += percent_step
                    message_pass_send += 1
                    message_count -= 1
                else:
                    # TODO support other address family
                    message_count -= 1
                    continue
            else:
                message_count -= 1
                continue

    # hashes = '#' * bar_length
    # spaces = ''
    # sys.stdout.write("\rPercent: [%s] %.2f%%"%(hashes + spaces, 100.00))
    # sys.stdout.flush()
    # print('\nTotal messages:   %s' % int(message_count))
    # print('Success send out: %s' % send_success)
    # print('Failed send out:  %s' % send_failed)

if __name__ == '__main__':

    CONF(args=sys.argv[1:])
    try:
        send_update()
    except KeyboardInterrupt:
        sys.exit()
