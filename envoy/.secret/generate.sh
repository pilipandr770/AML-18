#!/bin/bash

# Remove old keys if they exist
keyFiles=("server.gz" "counterparty.gz" "client.gz" "localhost.gz")
for keyfile in ${keyFiles}[@]}; do
    if [ -f $keyfile ]; then
        rm $keyfile
    fi
done

# Create CA
openssl req -x509 -newkey rsa:4096 -sha256 -days 10950 \
    -nodes -keyout ca.key -out ca.crt \
    -subj "/C=US/ST=California/L=Menlo Park/O=TRISA/OU=Localhost/CN=trisatest.dev" \
    -addext "subjectAltName=DNS:trisatest.dev,DNS:*.trisatest.dev"

# Create certificate requests for the server and the client
openssl req -new -newkey rsa:4096 \
    -nodes -keyout server.key.pem -out server.csr \
    -subj "/C=US/ST=Minnesota/L=Minneapolis/O=Localhost/OU=Testing/CN=envoy.local" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:envoy.local,IP:127.0.0.1"

openssl req -new -newkey rsa:4096 \
    -nodes -keyout counterparty.key.pem -out counterparty.csr \
    -subj "/C=DE/ST=Hesse/L=Frankfurt/O=Counterparty/OU=Testing/CN=counterparty.local" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:counterparty.local,IP:127.0.0.1"

openssl req -new -newkey rsa:4096 \
    -nodes -keyout client.key.pem -out client.csr \
    -subj "/C=US/ST=Georgia/L=Atlanta/O=Client/OU=Testing/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"

# Create signed certificates with CA.
#
# NOTE: `-copy_extensions copyall` requires OpenSSL 3.0+ (unavailable in,
# e.g., Git for Windows' bundled OpenSSL 1.1.1). Using -extfile with an
# explicit SAN instead works identically on 1.1.1 and 3.0+, so it's used
# here unconditionally rather than branching on openssl version. Written
# to real temp files rather than passed via `<(...)` process substitution:
# Git for Windows' bash/openssl combination doesn't reliably read from
# `/dev/fd/*` across the subprocess boundary process substitution relies
# on -- it fails intermittently (openssl reports "No such file or
# directory" but still exits 0), silently producing a signed cert with no
# SAN extension. Plain temp files have no such portability issue.
echo "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:envoy.local,IP:127.0.0.1" > server.ext
echo "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:counterparty.local,IP:127.0.0.1" > counterparty.ext
echo "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1" > client.ext

openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in server.csr -out server.pem \
    -extfile server.ext

openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in counterparty.csr -out counterparty.pem \
    -extfile counterparty.ext

openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in client.csr -out client.pem \
    -extfile client.ext

# Combine files into a single certificate chain
cat ca.crt >> server.pem
cat server.key.pem >> server.pem
gzip server.pem

cat ca.crt >> counterparty.pem
cat counterparty.key.pem >> counterparty.pem
gzip counterparty.pem

cat ca.crt >> client.pem
cat client.key.pem >> client.pem
gzip client.pem

mv ca.crt localhost.pem
gzip localhost.pem

# Cleanup
rm server.csr server.key.pem server.ext
rm counterparty.csr counterparty.key.pem counterparty.ext
rm client.csr client.key.pem client.ext
rm ca.key