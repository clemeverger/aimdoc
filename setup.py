from setuptools import setup, find_packages

setup(
    name='aimdoc',
    version='1.0.0',
    description='AI-friendly documentation scraper that produces Markdown for LLMs',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    install_requires=[
        'scrapy>=2.8.0',
        'beautifulsoup4>=4.11.0',
        'markdownify>=0.11.0',
        'lxml>=4.9.0',
        'requests>=2.28.0',
    ],
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Documentation',
        'Topic :: Text Processing :: Markup :: HTML',
    ],
    # No CLI entry points - use directly with scrapy command
)