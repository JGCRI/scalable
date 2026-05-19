Submitting Functions
====================

.. autoclass:: scalable.ScalableClient
    :exclude-members: submit, map, get_versions, cancel, close, gather

.. autofunction:: scalable.ScalableClient.submit

.. autofunction:: scalable.ScalableClient.map

.. autofunction:: scalable.ScalableClient.get_versions

.. autofunction:: scalable.ScalableClient.cancel

.. autofunction:: scalable.ScalableClient.close

Inherited Dask Client API
=========================

``ScalableClient`` extends ``distributed.Client`` and keeps core Dask client
behavior unchanged for methods not overridden by Scalable.

.. note::

   Methods such as ``gather`` are inherited directly from
   ``distributed.Client``.

.. autofunction:: distributed.Client.gather
