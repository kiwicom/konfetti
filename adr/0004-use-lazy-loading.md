# 4. Use lazy loading

Date: 2019-06-30

## Status

Accepted

## Context

We need to avoid side effects on configuration loading and prevent the need to fully configure the settings to run a subset of tests in projects using `konfetti`.

## Decision

We will use a lazy evaluation approach, similar to [implemented in Django](https://github.com/django/django/blob/master/django/conf/__init__.py#L42)

## Consequences

Configuration options could be specified lazily which will not produce side effects on imports (e.g. network requests) and will allow to specify only required subset of configuration in applications.
The access point is isolated in `Konfig` class and allows us to easily implement different extensions (caching, async evaluation) under different namespaces (`env`, `vault`, `lazy`).
