import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django-advanced-pdf",
    version="0.2.1",
    author="Thomas Turner",
    description="Django app that helps one create pdf",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/django-advance-utils/django-advanced-pdf",
    include_package_data=True,
    packages=['django_advanced_pdf'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
