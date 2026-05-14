import setuptools

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setuptools.setup(
    name="autossh",
    version="1.4.4",
    description="Auto-SSH toolkits with alias-based host management and password encryption",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/spgyip/autossh",
    author="supergui",
    author_email="supergui@live.cn",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Environment :: Console",
        "Topic :: System :: Networking",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=["pexpect", "pyyaml", "cryptography"],
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": [
            "assh    = autossh.cli.assh:main",
            "apush   = autossh.cli.apush:main",
            "apull   = autossh.cli.apull:main",
            "acat    = autossh.cli.acat:main",
            "aedit   = autossh.cli.aedit:main",
            "amaster = autossh.cli.amaster:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
