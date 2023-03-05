"""Setup package for py-pi"""

from setuptools import setup

setup(
    name='nozomipy-async',
    packages=['nozomi_async'],
    version='1.0.0',
    license='MIT',
    description='Nozomi Async API for retrieving images, videos, gifs.',
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author='Isotr0py',
    author_email='Isotr0py@outlook.com',
    url='https://github.com/Isotr0py/nozomi.la-async',
    keywords=['nozomi', 'nozomi.la', 'api', 'video', 'image', 'anime'],
    install_requires=[
        'aiohttp',
        'dacite',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
)