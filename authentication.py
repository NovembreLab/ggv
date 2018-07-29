
from functools import wraps
from flask import Flask
from flask import g, request, url_for, flash
from flask import redirect, url_for, render_template
from flask import jsonify
from flask_oauthlib.client import OAuth
from urlparse import urlparse

from ggv.main import app, session

oauth = OAuth()

twitter = oauth.remote_app(
    'twitter',
    consumer_key=app.config['YAML_CONFIG']['twitter']['key'],
    consumer_secret=app.config['YAML_CONFIG']['twitter']['secret'],
    base_url='https://api.twitter.com/1.1/',
    request_token_url='https://api.twitter.com/oauth/request_token',
    access_token_url='https://api.twitter.com/oauth/access_token',
    authorize_url='https://api.twitter.com/oauth/authorize'
)

google = oauth.remote_app(
    'google',
    consumer_key=app.config['YAML_CONFIG']['google']['key'],
    consumer_secret=app.config['YAML_CONFIG']['google']['secret'],
    request_token_params={
        'scope': 'email'
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)


@twitter.tokengetter
def get_twitter_token():
    if 'twitter_oauth' in session:
        resp = session['twitter_oauth']
        return resp['oauth_token'], resp['oauth_token_secret']

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')

@app.before_request
def before_request():
    g.user = None
    if 'twitter_oauth' in session:
        g.user = session['twitter_oauth']


@app.route('/login/<string:auth>')
def login(auth):
    if auth == 'twitter':
        callback_url = url_for('twitter_authorize', next=request.args.get('next'))
        return twitter.authorize(callback=callback_url or request.referrer or None)
    elif auth == 'google':
        return google.authorize(callback=url_for('google_authorize', _external=True))


@app.route('/logout')
def logout():
    session.pop('twitter_oauth', None)
    session.pop('google_token', None)
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/login/auth/twitter')
def twitter_authorize():
    resp = twitter.authorized_response()
    if resp is None:
        flash('You denied the request to sign in.')
    else:
        session['twitter_oauth'] = resp
        session['username'] = session['twitter_oauth']['screen_name']
        session['service'] = 'twitter'
    return redirect(url_for('index'))


@app.route('/login/auth/google')
def google_authorize():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')
    session['username'] = google.get('userinfo').data['email']
    session['service'] = 'google'
    return redirect(url_for('index'))


def login_required(func):
    """
    decorator that checks oauth token present in session.
    """
    @wraps(func)
    def inner(*args, **kwargs):
        access_confirm = app.config['YAML_CONFIG']['access_key']
        access_key = request.args.get('access_key', '')
        ref = ""
        if request.referrer:
            ref = urlparse(request.referrer)
            if ref.netloc.endswith("clinicalgenome.org") or ref.netloc.endswith("pharmgkb.org"):
                session['username'] = 'clinical_genome'
                session['service'] = 'API'
                return func(*args, **kwargs) # Explicit return here
        if access_key == access_confirm and access_key:
            session['username'] = 'access_key'
            session['service'] = 'API'
            return func(*args, **kwargs) # Explicit return here
        elif access_key != access_confirm and access_key:
            session.pop('username', None)
            session.pop('service', None)
            return redirect(url_for('welcome_login_page'))
        elif 'username' not in session:
            return redirect(url_for('welcome_login_page'))
        elif session['username'] == "access_key":
            session.pop('username', None)
        return func(*args, **kwargs)
    return inner