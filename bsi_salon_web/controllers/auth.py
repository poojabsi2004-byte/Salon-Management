# -*- coding: utf-8 -*-
"""Customer sign-in and registration for the Enrich site, on Odoo's own auth.

Nothing here stores or checks a credential itself. The pages are Odoo's
standard ``/web/login``, ``/web/signup`` and ``/web/reset_password`` (web +
auth_signup), restyled by views/bsi_salon_auth_templates.xml, and every account
is a real ``res.users``:

* Registering goes through auth_signup's own flow -- ``web_auth_signup`` ->
  ``do_signup`` -> ``res.users.signup()`` -> ``_signup_create_user()`` -- which
  copies the portal template user (``base.template_portal_user_id``). That one
  step creates the portal ``res.users`` (share=True, Portal group) *and* the
  ``res.partner`` it is linked to (name, email, and the mobile number collected
  here, stored on ``res.partner.phone`` -- the only phone field a v19 partner
  has, and the one the booking flow already reads). After the account is created
  the user is NOT auto-logged in; instead they are redirected to /web/login
  with a success message so they log in explicitly (register → login → site).
* Signing in is Odoo's normal session authentication of that ``res.users``.

What this file adds on top of the standard controller:

* the mobile number field (read into the signup qcontext, validated, and passed
  to ``signup()`` with the rest of the values);
* friendlier validation for a self-registration (a real email address, a real
  mobile number, the password policy checked up front so its message reads
  cleanly instead of being wrapped in "Could not create a new account");
* the post-login landing page: a customer (portal/share user) with no explicit
  ``?redirect=`` comes back to the site (/salon) instead of the stock portal
  /my page. An explicit ``?redirect=`` is honoured for everyone (Odoo's
  ``request.redirect`` keeps it on this host), and internal users with no
  redirect still get the backend, exactly as before.
"""

import logging
import re
import werkzeug
from werkzeug.urls import url_encode

from odoo import _, http, tools
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.website_sale.controllers.website import Website as WebsiteSaleWebsite

_logger = logging.getLogger(__name__)

# Where a customer lands after signing in when nothing asked for a specific page.
BSI_CUSTOMER_HOME = '/salon'

# A mobile number as people type it: digits with optional +, spaces, dashes,
# dots and brackets. 10-15 digits covers an Indian mobile (10) up to a full
# E.164 international number (15).
_PHONE_CHARS = re.compile(r'^\+?[\d\s().-]+$')
_PHONE_MIN_DIGITS = 10
_PHONE_MAX_DIGITS = 15


class BsiSalonLoginRedirect(WebsiteSaleWebsite):
    """Where to go after signing in.

    Subclasses website_sale's Website controller (not web's Home) on purpose:
    Odoo builds the final /web/login controller from every leaf subclass of
    Home, and both website and portal override ``_login_redirect`` to send a
    customer with no redirect to the portal's /my page. Only a subclass of the
    most-derived of those is guaranteed (by the MRO) to run before them.
    """

    def _login_redirect(self, uid, redirect=None):
        # Only the "nothing asked for" case changes, and only for customers;
        # internal users with no redirect still get the backend (/odoo).
        if not redirect and not is_user_internal(uid):
            redirect = BSI_CUSTOMER_HOME
        return super()._login_redirect(uid, redirect=redirect)


class BsiSalonAuth(AuthSignupHome):
    """Registration: the mobile number field and friendlier validation."""

    def get_auth_signup_qcontext(self):
        qcontext = super().get_auth_signup_qcontext()
        # SIGN_UP_REQUEST_PARAMS has no phone key, so the standard qcontext
        # drops it; keep it so it reaches do_signup and survives a re-render
        # after a validation error.
        phone = request.params.get('phone')
        if phone is not None:
            qcontext['phone'] = phone.strip()
        return qcontext

    @staticmethod
    def _bsi_invalid(qcontext, field, message):
        """Refuse the form, remembering which field to highlight on re-render."""
        qcontext['bsi_error_field'] = field
        raise UserError(message)

    def _prepare_signup_values(self, qcontext):
        try:
            values = super()._prepare_signup_values(qcontext)
        except UserError:
            # the only check upstream makes on a filled-in form: the two passwords
            qcontext['bsi_error_field'] = 'confirm_password'
            raise
        Users = request.env['res.users'].sudo()
        # Invitation / password-reset links carry a token and already have a
        # partner; only a fresh self-registration needs the full checks.
        is_registration = not qcontext.get('token')
        if is_registration:
            name = (values.get('name') or '').strip()
            login = (values.get('login') or '').strip()
            if not name:
                self._bsi_invalid(qcontext, 'name', _("Please enter your full name."))
            if not login or not tools.single_email_re.match(login):
                self._bsi_invalid(qcontext, 'login', _("Please enter a valid email address, e.g. name@example.com."))
            # Same lookup _signup_create_user makes, done first so the form can
            # point at the email field and say what to do instead.
            if Users.with_context(active_test=False).search_count(
                    Users._get_login_domain(login) | Users._get_email_domain(login), limit=1):
                self._bsi_invalid(qcontext, 'login', _(
                    "An account with this email already exists. Log in instead, "
                    "or use \"Forgot password?\" to set a new password."))
            values.update(name=name, login=login)

        phone = (qcontext.get('phone') or '').strip()
        if phone:
            digits = re.sub(r'\D', '', phone)
            if not _PHONE_CHARS.match(phone) or not (_PHONE_MIN_DIGITS <= len(digits) <= _PHONE_MAX_DIGITS):
                self._bsi_invalid(qcontext, 'phone', _(
                    "Please enter a valid mobile number (at least %s digits).", _PHONE_MIN_DIGITS))
            # res.users _inherits res.partner, so this lands on the partner.
            values['phone'] = phone
        elif is_registration:
            self._bsi_invalid(qcontext, 'phone', _(
                "Please enter your mobile number so the salon can reach you about bookings."))

        # Odoo's own password policy (auth_password_policy), checked before the
        # account is created so its message is shown as-is.
        if values.get('password') and hasattr(Users, '_check_password_policy'):
            try:
                Users._check_password_policy([values['password']])
            except UserError:
                qcontext['bsi_error_field'] = 'password'
                raise
        return values

    @http.route()
    def web_auth_signup(self, *args, **kw):
        """Register the account without auto-login, then redirect to the login
        page with a success notice so the customer signs in explicitly.

        Flow: /web/signup (POST) → account created, no session → /web/login?registered=1
        """
        qcontext = self.get_auth_signup_qcontext()

        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()

        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                # Create the account; do_login=False skips session.authenticate
                # so the new user is NOT signed in automatically.
                self.do_signup(qcontext, do_login=False)

                # Send the creation-confirmation email (same as the core does).
                User = request.env['res.users']
                user_sudo = User.sudo().search(
                    User._get_login_domain(qcontext.get('login')),
                    order=User._get_login_order(),
                    limit=1,
                )
                template = request.env.ref(
                    'auth_signup.mail_template_user_signup_account_created',
                    raise_if_not_found=False,
                )
                if user_sudo and template:
                    template.sudo().send_mail(user_sudo.id, force_send=True)

                # Redirect to the login page; web_login below adds the message.
                return request.redirect('/web/login?registered=1')
            except UserError as e:
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                User = request.env['res.users']
                if User.sudo().with_context(active_test=False).search_count(
                        User._get_login_domain(qcontext.get('login')), limit=1):
                    qcontext['error'] = _("Another user is already registered using this email address.")
                else:
                    _logger.warning("%s", e)
                    qcontext['error'] = _("Could not create a new account.")

        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search(
                [('email', '=', qcontext.get('signup_email')), ('state', '!=', 'new')], limit=1)
            if user:
                return request.redirect('/web/login?%s' % url_encode({'login': user.login, 'redirect': '/web'}))

        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @http.route()
    def web_login(self, *args, **kw):
        """Show a success banner when landing from the registration redirect."""
        response = super().web_login(*args, **kw)
        if (not request.session.uid
                and request.params.get('registered')
                and hasattr(response, 'qcontext')):
            response.qcontext['message'] = _("Account created successfully. Please log in to continue.")
        return response
