"""
 Usage:
 A call to http://localhost:80000/test will cache in memcache for TTL seconds
 and not redownload it again. Host, port and TTL may be configured via
 command line arguments or via configuration file.
 To stop the server simply send SIGINT (Ctrl-C). It does not handle any headers or post data.

"""

import argparse
import BaseHTTPServer
import ConfigParser
import logging
import memcache
import requests


CONF_FILE = 'proxy_server.cfg'
REQUEST_TIMEOUT = 408
SERVICE_UNAVAILABLE = 503

log = logging.getLogger(__name__) # pylint: disable=invalid-name


class CachingServer(BaseHTTPServer.HTTPServer):
    """
    Wrapper for HTTPServer to make it possible
    to server memcached configs.
    """
    def __init__(self, *args, **kwargs):
        self._mc_host = kwargs.pop("mc_host")
        self._mc_port = kwargs.pop("mc_port")
        self._ttl = kwargs.pop("ttl")
        BaseHTTPServer.HTTPServer.__init__(self, *args, **kwargs)


class CachingHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """ Custom handler for caching proxy server. """

    def __init__(self, *args, **kwargs):
        # Setup memcache client

        # Trick: read memcached configs from CachingServer instance
        socket_obj, server, cache_server = args
        self._ttl = cache_server._ttl
        mc_host = cache_server._mc_host
        mc_port = cache_server._mc_port

        self._mc = memcache.Client([(mc_host, mc_port)])

        BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self): # pylint: disable=invalid-name
        """ Overwrite do_GET method. """
        data = ''
        if self._mc.get(self.path):
            # Get response from memcache
            data = self._mc.get(self.path)
            status_code = data.status_code # pylint: disable=no-member
        else:
            # Setup proxy server request URL
            host, port = self.server.server_address
            proxy_server = 'http://{0}:{1}'.format(host, port)
            url = proxy_server + self.path
            try:
                # Fetch data from the proxy server and add it to memcache
                data = requests.get(url, timeout=20)
                self._mc.set(self.path, data, time=self._ttl)
                status_code = data.status_code
            except requests.exceptions.ConnectionError as e: # pylint: disable=invalid-name
                log.error(e)
                status_code = SERVICE_UNAVAILABLE
            except requests.exceptions.Timeout as e: # pylint: disable=invalid-name
                log.error(e)
                status_code = REQUEST_TIMEOUT

        # Send response to the client
        self.send_response(status_code)
        self.end_headers()
        self.wfile.writelines(data)


def read_configs(filename):
    """ Read configurations from configuration file. """
    conf = ConfigParser.ConfigParser()
    conf.read(filename)
    host = conf.get('proxy_server', 'host')
    port = conf.getint('proxy_server', 'port')
    ttl = conf.getint('proxy_server', 'TTL')
    return host, port, ttl


def read_mc_conf(filename):
    """Read configuration for memcached. """
    conf = ConfigParser.ConfigParser()
    conf.read(filename)
    mc_host = conf.get('memcached', 'host')
    mc_port = conf.getint('memcached', 'port')
    return mc_host, mc_port


def parse_args():
    """ Parse arguments from a command line. """
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", action="store",
                        help="setup proxy server(via IP address)")
    parser.add_argument("-p", "--port", action="store", type=int,
                        help="setup port of proxy server")
    parser.add_argument("-t", "--ttl", action="store", type=int,
                        help="time for caching requests")
    args = parser.parse_args()
    return args.server, args.port, args.ttl


def run():
    """ Run a simple proxy server with caching. """
    host, port, ttl = parse_args()

    # Read memcached configs
    mc_host, mc_port = read_mc_conf(CONF_FILE)

    if not all([host, port, ttl]):
        print "Used configuration file: proxy_server.cfg"

        # Load configs from config file
        host, port, ttl, mc_host, mc_port = read_configs(CONF_FILE)

    # Run proxy server.
    httpd = CachingServer((host, port), CachingHandler,
                          mc_host=mc_host, mc_port=mc_port, ttl=ttl)
    httpd.serve_forever()

if __name__ == '__main__':
    run()
