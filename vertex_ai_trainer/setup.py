from setuptools import setup, find_packages

setup(
    name='vertex_ai_trainer',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'timm==0.9.12',
        'mplfinance==0.9.0',
        'yfinance==0.2.37',
        'google-cloud-storage==2.15.0'
    ],
    description='Vertex AI Training Package',
)
