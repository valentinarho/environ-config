from __future__ import absolute_import, division, print_function

import attr
import pytest

import environ

from environ._environ_config import _SecretStr


@environ.config(prefix="XYZ", vault_prefix="ABC")
class Nested(object):
    """
    A nested configuration example.
    """
    @environ.config
    class Sub(object):
        y = environ.var()
        z = environ.vault_var()

    x = environ.var()
    sub = environ.group(Sub)


class TestEnvironConfig(object):
    def test_empty(self):
        """
        Empty config is accepted.
        """
        @environ.config
        class Empty(object):
            pass

        cfg = environ.to_config(Empty)

        assert "Empty()" == repr(cfg)

    def test_flat(self):
        """
        Flat config is extracted.
        """
        @environ.config(prefix="APP")
        class Flat(object):
            x = environ.var()
            y = environ.var()

        cfg = environ.to_config(Flat, environ={
            "APP_X": "foo",
            "APP_Y": "bar",
        })

        assert Flat(x="foo", y="bar") == cfg

    @pytest.mark.parametrize("debug", [True, False])
    def test_nested(self, debug, capsys):
        """
        Nested config is extracted, prefix and vault_prefix are propagated. If
        debug is True, the variable names are printed out as we look for them.
        """
        env = {
            "APP_X": "nope",
            "XYZ_X": "foo",
            "XYZ_SUB_Y": "bar",
            "SECRET_ABC_SUB_Z": "qux",
        }
        debug_err = """\
environ_config: variables found: %r.
environ_config: looking for 'XYZ_X'.
environ_config: looking for 'XYZ_SUB_Y'.
environ_config: looking for 'SECRET_ABC_SUB_Z'.
""" % (list(env.keys()),)

        cfg = environ.to_config(Nested, environ=env, debug=debug)

        assert Nested(x="foo", sub=Nested.Sub(y="bar", z="qux")) == cfg

        if debug:
            assert ("", debug_err) == capsys.readouterr()
        else:
            assert ("", "") == capsys.readouterr()

    @pytest.mark.parametrize("debug", [True, False])
    def test_missing(self, debug, capsys):
        """
        If a var is missing, a human-readable MissingEnvValueError is raised.
        """
        debug_err = """\
environ_config: variables found: ['y'].
environ_config: looking for 'APP_X'.
"""

        @environ.config
        class Mandatory(object):
            x = environ.var()

        with pytest.raises(environ.MissingEnvValueError) as e:
            environ.to_config(Mandatory, environ={"y": "boring"}, debug=debug)

        assert ("APP_X",) == e.value.args

        if debug:
            assert ("", debug_err) == capsys.readouterr()
        else:
            assert ("", "") == capsys.readouterr()

    def test_default(self):
        """
        Default values are used iff the vars are missing.
        """
        @environ.config
        class Defaults(object):
            x = environ.var("foo")
            y = environ.var("qux")

        cfg = environ.to_config(Defaults, environ={
            "APP_Y": "bar",
        })

        assert Defaults(x="foo", y="bar") == cfg

    def test_vault_env_template(self):
        """
        {env} in vault_prefix gets recursively replaced by an actual
        uppercased ENV.
        """
        @environ.config(vault_prefix="XYZ_{env}_ABC")
        class WithEnv(object):
            env = environ.var()
            password = environ.vault_var()

        cfg = environ.to_config(WithEnv, environ={
            "APP_ENV": "foo",
            "SECRET_XYZ_FOO_ABC_PASSWORD": "bar",
        })

        assert "bar" == cfg.password

    def test_secret_str_no_repr(self):
        """
        Outside of reprs, _SecretStr behaves normally.
        """
        s = _SecretStr("abc")

        assert "'abc'" == repr(s)

    def test_secret_str_censors(self):
        """
        _SecretStr censors it's __repr__ if its called from another __repr__.
        """
        s = _SecretStr("abc")

        @attr.s
        class C(object):
            s = attr.ib()

        assert "C(s=<SECRET>)" == repr(C(s))

    @pytest.mark.parametrize("prefix", [None, ""])
    def test_no_prefix(self, prefix):
        """
        If prefix is None or "", don't add a leading _ when adding namespaces.
        """
        @environ.config(prefix=prefix, vault_prefix=prefix)
        class C(object):
            x = environ.var()
            s = environ.vault_var()

        cfg = environ.to_config(C, environ={
            "X": "foo",
            "SECRET_S": "bar",
        })

        assert C("foo", "bar") == cfg

    def test_overwrite(self):
        """
        The env variable name can be overwritten.
        """
        @environ.config
        class C(object):
            x = environ.var(name="LANG")
            y = environ.var()

        cfg = environ.to_config(C, environ={
            "APP_X": "nope",
            "LANG": "foo",
            "APP_Y": "bar",
        })

        assert C("foo", "bar") == cfg

    def test_debug_env(self, capsys):
        """
        Setting "ENVIRON_CONFIG_DEBUG" has the same effect as passing True to
        `debug`.
        """
        debug_err = """\
environ_config: variables found: ['ENVIRON_CONFIG_DEBUG'].
"""

        @environ.config
        class C(object):
            pass

        env = {
            "ENVIRON_CONFIG_DEBUG": "1",
        }

        environ.to_config(C, environ=env, debug=False)

        assert ("", debug_err,) == capsys.readouterr()
