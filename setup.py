import setuptools

setuptools.setup(name="autossh",
        version="1.4.4",
        description="Auto-SSH toolkits",
        url="https://github.com/spgyip/autossh",
        author="supergui",
        author_email="supergui@live.cn",
        license="MIT",
        python_requires=">=3.6",
        install_requires=['pexpect', 'pyyaml'],
        packages=setuptools.find_packages(),
        scripts=["bin/assh", "bin/apush", "bin/apull", "bin/acat", "bin/aedit", "bin/qssh"],
        include_package_data=True,
        zip_safe=False)
