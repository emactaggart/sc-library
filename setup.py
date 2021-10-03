from setuptools import setup

setup(
    name='sc-library',
    version='0.1',
    description='',
    license='TODO',
    packages=['TODO'],
    author='Evan MacTaggart',
    author_email='evan.mactaggart@gmail.com',
    install_requires=['click'],
    keywords=["soundcloud", "library"],
    # FIXME url='https://github.com/emactaggart/sc-library',
    entry_points={
        'console_scripts':['sc-library=sc-library:start']
    }
)
