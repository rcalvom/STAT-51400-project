from dotenv import load_dotenv
from together import Together
import os

load_dotenv()
client = Together(api_key="tgp_v1_20hvBht1T6ZGirABJShui8aUtErdvgNLChGeLVTGEVo")
client.models.list()
