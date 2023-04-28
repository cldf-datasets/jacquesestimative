from setuptools import setup


setup(
    name='cldfbench_jacquesestimative',
    py_modules=['cldfbench_jacquesestimative'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'cldfbench.dataset': [
            'jacquesestimative=cldfbench_jacquesestimative:Dataset',
        ]
    },
    install_requires=[
        'cldfbench[glottolog]',
    ],
    extras_require={
        'test': [
            'pytest-cldf',
        ],
    },
)
