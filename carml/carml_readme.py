import pkg_resources
import click


async def run(reactor, cfg, tor):
    readme = pkg_resources.resource_string('carml', '../README.rst')
    # uhm, docutils documentation is confusing as all hell and no good
    # examples of "convert this rST string to anything else" .. :/ but
    # we should "render" it to text
    click.echo_via_pager(readme.decode('utf8'))
