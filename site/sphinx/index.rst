Image Toolkit — Python Backend Reference
=========================================

This Sphinx reference is generated from the ``backend/src/`` module tree by
`sphinx-autoapi <https://sphinx-autoapi.readthedocs.io>`_ and documents every
public class, function, and constant via their Google-style docstrings.

.. note::

   **Relationship to the MkDocs portal** — The MkDocs Material portal at
   ``docs/`` provides per-module API stubs via ``mkdocstrings`` (lighter-weight,
   integrated with the roadmap and changelog pages).  This Sphinx build is the
   *comprehensive* reference — all modules discovered automatically, with
   cross-links to NumPy, PyTorch, and the Python stdlib.

   Build locally::

      sphinx-build -b html docs/sphinx site/sphinx-api
      open site/sphinx-api/index.html

.. toctree::
   :maxdepth: 3
   :caption: Python API Reference

   autoapi/index

.. toctree::
   :maxdepth: 1
   :caption: Notebooks (static)

   ../../docs/notebooks/benchmark_analysis
   ../../docs/notebooks/asp_pipeline_walkthrough
   ../../docs/notebooks/clip_embedding_walkthrough
