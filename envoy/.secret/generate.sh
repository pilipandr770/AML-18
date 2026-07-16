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
# here unconditionally rather than branching on openssl version.
openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in server.csr -out server.pem \
    -extfile <(printf "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:envoy.local,IP:127.0.0.1")

openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in counterparty.csr -out counterparty.pem \
    -extfile <(printf "subjectAltName=DNS:localhost,DNS:*.localhost,DNS:counterparty.local,IP:127.0.0.1")

openssl x509 -req -days 10950 \
    -CA ca.crt -CAkey ca.key \
    -in client.csr -out client.pem \
    -extfile <(printf "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1")

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
rm server.csr server.key.pem
rm counterparty.csr counterparty.key.pem
rm client.csr client.key.pem
rm ca.key