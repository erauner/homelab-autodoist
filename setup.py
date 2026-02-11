from setuptools import setup, find_packages

setup(
    name='autodoist',
    version='2.0.0',
    packages=find_packages(exclude=['tests', 'tests.*']),
    url='https://github.com/Hoffelhas/automation-todoist',
    license='MIT',
    author='Alexander Haselhoff',
    author_email='xela@live.nl',
    description='GTD automation for Todoist: automatic next-action labeling',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    python_requires='>=3.9',
    install_requires=[
        'todoist-api-python>=3.0.0',
        'requests>=2.28.1',
    ],
    extras_require={
        'dev': [
            'pytest>=7.0.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'autodoist=autodoist.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
