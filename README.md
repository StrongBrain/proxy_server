# Proxy Server
Simple caching Proxy Server
### Travis CI Status
[![Build Status](https://travis-ci.org/StrongBrain/proxy_server.svg)](https://travis-ci.org/StrongBrain/proxy_server)


# Quick start

After downloading of sources follow these steps:

1. Install memcached:

   `sudo apt-get install memcached`

2. Make sure, memcached is running:

   `sudo  /etc/init.d/memcached status`

3. Check usage of running script:

   `python server.py --help`

4. Run starting script:

   `python server.py -s 127.0.0.1 -p 8000 -t 15`

   or without command line arguments(in this case all parameters gets from configuration file):

   `python server.py`

5. Try to send few requests to proxy server and make sure that caching is working fine.
