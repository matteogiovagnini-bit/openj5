# OpenJ5 TLS Certificates

Generate certificates for production with:

```powershell
# Certificate Authority
openssl req -new -x509 -days 3650 -extensions v3_ca -keyout ca.key -out ca.crt

# Mosquitto broker
openssl genrsa -out mosquitto.key 2048
openssl req -new -key mosquitto.key -out mosquitto.csr
openssl x509 -req -in mosquitto.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out mosquitto.crt -days 365

# Node certificates (node1-node6)
openssl genrsa -out node1.key 2048
openssl req -new -key node1.key -out node1.csr
openssl x509 -req -in node1.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out node1.crt -days 365

# API certificate
openssl genrsa -out api.key 2048
openssl req -new -key api.key -out api.csr
openssl x509 -req -in api.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out api.crt -days 365

# JWT signing keys
openssl genpkey -algorithm RSA -out jwt_private.pem -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in jwt_private.pem -out jwt_public.pem
```

Required files:
- ca.crt, ca.key
- mosquitto.crt, mosquitto.key
- node1.crt, node1.key (for node2-6 also)
- api.crt, api.key
- rosbridge.crt, rosbridge.key
- jwt_public.pem
