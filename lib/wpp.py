"""
Web Pay Plus
"""
import os
import unidecode

import asyncio
import aiohttp

from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import requests

from lib.AESEncryption import AES128Encryption

load_dotenv()  # Take environment variables from .env


def create_chain_xml(amount, email, description, client_id):
    """Crear cadena XML"""
    root = ET.Element("P")

    business = ET.SubElement(root, "business")
    ET.SubElement(business, "id_company").text = "SNBX"
    ET.SubElement(business, "id_branch").text = "01SNBXBRNCH"
    ET.SubElement(business, "user").text = "SNBXUSR01"
    ET.SubElement(business, "pwd").text = "SECRETO"

    url = ET.SubElement(root, "url")
    ET.SubElement(url, "reference").text = "FACTURA999"
    ET.SubElement(url, "amount").text = str(amount)
    ET.SubElement(url, "moneda").text = "MXN"
    ET.SubElement(url, "canal").text = "W"
    ET.SubElement(url, "omitir_notif_default").text = "1"
    ET.SubElement(url, "st_correo").text = "1"
    ET.SubElement(url, "fh_vigencia").text = "14/07/2022"
    ET.SubElement(url, "mail_cliente").text = email
    ET.SubElement(url, "st_cr").text = "A"

    data = ET.SubElement(url, "datos_adicionales")
    data1 = ET.SubElement(data, "data")
    data1.attrib["id"] = "1"
    data1.attrib["display"] = "true"
    label1 = ET.SubElement(data1, "label")
    label1.text = description
    value1 = ET.SubElement(data1, "value")
    value1.text = str(client_id)

    ET.SubElement(url, "version").text = "IntegraWPP"

    return ET.tostring(root, encoding="utf-8")


def encrypt_chain(chain: str):
    """Cifrar cadena XML"""
    key = os.getenv("WPP_KEY")
    if key is None:
        return None
    aes_encryptor = AES128Encryption()
    ciphertext = aes_encryptor.encrypt(chain, key)
    return ciphertext


def decrypt_chain(chain_encrypted: str):
    """Descifrar cadena XML"""
    key = os.getenv("WPP_KEY")
    if key is None:
        return None
    aes_encryptor = AES128Encryption()
    plaintext = aes_encryptor.decrypt(key, chain_encrypted)
    return plaintext


async def send(chain: str):
    """Send to WPP"""

    # Get the commerce ID
    commerce_id = os.getenv("WPP_COMMERCE_ID")
    if commerce_id is None:
        return None

    # Get the WPP URL
    wpp_url = os.getenv("WPP_URL")
    if wpp_url is None:
        return None

    # Pack the chain
    root = ET.Element("pgs")
    data0 = ET.SubElement(root, "data0")
    data0.text = commerce_id
    data = ET.SubElement(root, "data")
    data.text = chain
    chain_bytes = ET.tostring(root, encoding="utf-8")

    # Send the chain
    async with aiohttp.ClientSession() as session:
        async with session.post(wpp_url, data=chain_bytes) as resp:
            return await resp.text()


if __name__ == "__main__":
    chain = create_chain_xml(
        amount=100.0,
        email="guivaloz@gmail.com",
        description="Test",
        client_id="123456789",
    )
    print(chain)
