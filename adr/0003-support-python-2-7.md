# 3. Support Python 2.7

Date: 2019-06-30

## Status

Accepted

## Context

We need to help application developers to migrate their projects from Python 2.7 to 3.5+.

## Decision

We will support Python 2.7 on the best effort level until 2020-01-01.

## Consequences

Application written in Python 2.7 will be able to use lazy configuration via `konfetti`, which will simplify writing tests and porting the code to newer Python versions.
The costs of maintaining the compatibility code are tolerable, but types are harder to annotate.
