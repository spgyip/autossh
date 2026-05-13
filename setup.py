import setuptools

setuptools.setup(name="autossh",
        version="1.4.4",
        description="Auto-SSH toolkits",
        url="https://github.com/spgyip/autossh",
        author="supergui",
        author_email="supergui@live.cn",
        license="MIT",
        python_requires=">=3.6",
        install_requires=['pexpect', 'pyyaml', 'cryptography'],
        packages=setuptools.find_packages(),
        entry_points={
            "console_scripts": [
                "assh  = autossh.cli.assh:main",
                "apush = autossh.cli.apush:main",
                "apull = autossh.cli.apull:main",
                "acat  = autossh.cli.acat:main",
                "aedit   = autossh.cli.aedit:main",
                "amaster = autossh.cli.amaster:main",
            ],
        },
        include_package_data=True,
        zip_safe=False)
