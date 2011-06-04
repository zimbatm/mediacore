"""Setup the MediaCore application"""
import logging
import os.path
import random
import string

import pylons
import pylons.test

from genshi.template import NewTextTemplate
from genshi.template.loader import TemplateLoader
from PIL import Image
from migrate.versioning.api import (drop_version_control, version_control,
    version, upgrade)
from migrate.versioning.exceptions import DatabaseAlreadyControlledError

from mediacore.config.environment import load_environment
from mediacore.lib.i18n import N_
from mediacore.lib.storage import (BlipTVStorage, DailyMotionStorage,
    GoogleVideoStorage, LocalFileStorage, RemoteURLStorage, VimeoStorage,
    YoutubeStorage)
from mediacore.model import (Author, AuthorWithIP, Category, Comment,
    DBSession, Group, Media, MediaFile, Permission, Podcast, Setting,
    User, metadata, cleanup_players_table)

log = logging.getLogger(__name__)
here = os.path.dirname(__file__)

migrate_repository = os.path.join(here, 'migrations')

appearance_settings = [
    (u'appearance_logo', u''),
    (u'appearance_background_image', u''),
    (u'appearance_background_color', u'#fff'),
    (u'appearance_link_color', u'#0f7cb4'),
    (u'appearance_visited_link_color', u'#0f7cb4'),
    (u'appearance_text_color', u'#637084'),
    (u'appearance_navigation_bar_color', u'purple'),
    (u'appearance_heading_color', u'#3f3f3f'),
    (u'appearance_enable_cooliris', u'True'),
    (u'appearance_enable_featured_items', u'True'),
    (u'appearance_enable_podcast_tab', u'True'),
    (u'appearance_enable_user_uploads', u'True'),
    (u'appearance_display_logo', u'True'),
    (u'appearance_enable_widescreen_view', u''),
    (u'appearance_display_background_image', u'True'),
    (u'appearance_custom_css', u''),
    (u'appearance_custom_header_html', u''),
    (u'appearance_custom_footer_html', u''),
    (u'appearance_display_mediacore_footer', u'True'),
    (u'appearance_display_mediacore_credits', u'True'),
    (u'appearance_show_download', u'True'),
    (u'appearance_show_share', u'True'),
    (u'appearance_show_embed', u'True'),
    (u'appearance_show_widescreen', u'True'),
    (u'appearance_show_popout', u'True'),
    (u'appearance_show_like', u'True'),
    (u'appearance_show_dislike', u'True'),
]

def setup_app(command, conf, vars):
    """Called by ``paster setup-app``.

    This script is responsible for:

        * Creating the initial database schema and loading default data.
        * Executing any migrations necessary to bring an existing database
          up-to-date. Your data should be safe but, as always, be sure to
          make backups before using this.
        * Re-creating the default database for every run of the test suite.

    XXX: All your data will be lost IF you run the test suite with a
         config file named 'test.ini'. Make sure you have this configured
         to a different database than in your usual deployment.ini or
         development.ini file because all database tables are dropped a
         and recreated every time this script runs.

    XXX: If you are upgrading from MediaCore v0.7.2 or v0.8.0, run whichever
         one of these that applies:
           ``python batch-scripts/upgrade/upgrade_from_v072.py deployment.ini``
           ``python batch-scripts/upgrade/upgrade_from_v080.py deployment.ini``

    XXX: For search to work, we depend on a number of MySQL triggers which
         copy the data from our InnoDB tables to a MyISAM table for its
         fulltext indexing capability. Triggers can only be installed with
         a mysql superuser like root, so you must run the setup_triggers.sql
         script yourself.

    """
    if pylons.test.pylonsapp:
        # NOTE: This extra filename check may be unnecessary, the example it is
        # from did not check for pylons.test.pylonsapp. Leaving it in for now
        # to make it harder for someone to accidentally delete their database.
        filename = os.path.split(conf.filename)[-1]
        if filename == 'test.ini':
            log.info('Dropping existing tables...')
            metadata.drop_all(checkfirst=True)
            drop_version_control(conf.local_conf['sqlalchemy.url'],
                                 migrate_repository)
    else:
        # Don't reload the app if it was loaded under the testing environment
        config = load_environment(conf.global_conf, conf.local_conf)

    # Create the migrate_version table if it doesn't exist.
    # If the table doesn't exist, we assume the schema was just setup
    # by this script and therefore must be the latest version.
    latest_version = version(migrate_repository)
    try:
        version_control(conf.local_conf['sqlalchemy.url'],
                        migrate_repository,
                        version=latest_version)
    except DatabaseAlreadyControlledError:
        log.info('Running any new migrations, if there are any')
        upgrade(conf.local_conf['sqlalchemy.url'],
                migrate_repository,
                version=latest_version)
    else:
        log.info('Initializing new database with version %r' % latest_version)
        metadata.create_all(bind=DBSession.bind, checkfirst=True)
        add_default_data()

    cleanup_players_table(enabled=True)

    # Save everything, along with the dummy data if applicable
    DBSession.commit()

    log.info('Generating appearance.css from your current settings')
    settings = DBSession.query(Setting.key, Setting.value)
    generate_appearance_css(settings, cache_dir=conf['cache_dir'])

    log.info('Successfully setup')

def random_string(length):
    return u"".join([random.choice(string.letters+string.digits) for x in range(1, length)])

def add_default_data():
    log.info('Adding default data')

    settings = [
        (u'email_media_uploaded', None),
        (u'email_comment_posted', None),
        (u'email_support_requests', None),
        (u'email_send_from', u'noreply@localhost'),
        (u'wording_user_uploads', N_(u"Upload your media using the form below. We'll review it and get back to you.")),
        (u'wording_administrative_notes', None),
        (u'wording_display_administrative_notes', u''),
        (u'popularity_decay_exponent', u'4'),
        (u'popularity_decay_lifetime', u'36'),
        (u'rich_text_editor', u'tinymce'),
        (u'google_analytics_uacct', u''),
        (u'featured_category', u'1'),
        (u'max_upload_size', u'314572800'),
        (u'ftp_storage', u'false'),
        (u'ftp_server', u'ftp.someserver.com'),
        (u'ftp_user', u'username'),
        (u'ftp_password', u'password'),
        (u'ftp_upload_directory', u'media'),
        (u'ftp_download_url', u'http://www.someserver.com/web/accessible/media/'),
        (u'ftp_upload_integrity_retries', u'10'),
        (u'akismet_key', u''),
        (u'akismet_url', u''),
        (u'req_comment_approval', u''),
        (u'use_embed_thumbnails', u'true'),
        (u'api_secret_key_required', u'true'),
        (u'api_secret_key', random_string(20)),
        (u'api_media_max_results', u'50'),
        (u'api_tree_max_depth', u'10'),
        (u'general_site_name', u'MediaCore'),
        (u'general_site_title_display_order', u'prepend'),
        (u'sitemaps_display', u'True'),
        (u'rss_display', u'True'),
        (u'vulgarity_filtered_words', u''),
        (u'primary_language', u'en'),
        (u'advertising_banner_html', u''),
        (u'advertising_sidebar_html', u''),
        (u'comments_engine', u'mediacore'),
        (u'facebook_appid', u''),
	(u'disqus_shortname', u''),
    ]
    settings.extend(appearance_settings)

    for key, value in settings:
        s = Setting()
        s.key = key
        s.value = value
        DBSession.add(s)

    admin_user = User()
    admin_user.user_name = u'admin'
    admin_user.display_name = u'Admin'
    admin_user.email_address = u'admin@somedomain.com'
    admin_user.password = u'admin'
    DBSession.add(admin_user)

    admin_group = Group()
    admin_group.group_name = u'admins'
    admin_group.display_name = u'Admins'
    admin_group.users.append(admin_user)
    DBSession.add(admin_group)

    editor_group = Group()
    editor_group.group_name = u'editors'
    editor_group.display_name = u'Editors'
    DBSession.add(editor_group)

    admin_perm = Permission()
    admin_perm.permission_name = u'admin'
    admin_perm.description = u'Grants access to the admin panel'
    admin_perm.groups.append(admin_group)
    DBSession.add(admin_perm)

    edit_perm = Permission()
    edit_perm.permission_name = u'edit'
    edit_perm.description = u'Grants access to edit site content'
    edit_perm.groups.append(admin_group)
    edit_perm.groups.append(editor_group)
    DBSession.add(edit_perm)

    category = Category()
    category.name = u'Featured'
    category.slug = u'featured'
    DBSession.add(category)

    category2 = Category()
    category2.name = u'Instructional'
    category2.slug = u'instructional'
    DBSession.add(category2)

    podcast = Podcast()
    podcast.slug = u'hello-world'
    podcast.title = u'Hello World'
    podcast.subtitle = u'My very first podcast!'
    podcast.description = u"""<p>Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>"""
    podcast.category = u'Technology'
    podcast.author = Author(admin_user.display_name, admin_user.email_address)
    podcast.explicit = None
    podcast.copyright = u'Copyright 2009 Xyz'
    podcast.itunes_url = None
    podcast.feedburner_url = None
    DBSession.add(podcast)

    comment = Comment()
    comment.subject = u'Re: New Media'
    comment.author = AuthorWithIP(name=u'John Doe', ip=2130706433)
    comment.body = u'<p>Hello to you too!</p>'
    DBSession.add(comment)

    media = Media()
    media.type = None
    media.slug = u'new-media'
    media.reviewed = True
    media.encoded = False
    media.publishable = False
    media.title = u'New Media'
    media.subtitle = None
    media.description = u"""<p>Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.</p>"""
    media.description_plain = u"""Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."""
    media.author = Author(admin_user.display_name, admin_user.email_address)
    media.categories.append(category)
    media.comments.append(comment)
    DBSession.add(media)

    #XXX The list of default players is actually defined in model.players
    # and should at some point be moved here to avoid inconsistency
    # between the default storage engines and default players.
    remote_url_storage = RemoteURLStorage()
    default_engines = [
        LocalFileStorage(),
        remote_url_storage,
        YoutubeStorage(),
        VimeoStorage(),
        BlipTVStorage(),
        DailyMotionStorage(),
        GoogleVideoStorage(),
    ]
    for engine in default_engines:
        DBSession.add(engine)

    import datetime
    instructional_media = [
        (u'workflow-in-mediacore',
        u'Workflow in MediaCore',
        u'<p>This sceencast explains the publish status feature in MediaCore.</p><p>Initially all videos uploaded through the front-end or admin panel are placed under &quot;awaiting review&quot; status. Once the administrator hits the &quot;review complete&quot; button, they can upload media. Videos can be added in any format, however, they can only be published if they are in a web-ready format such as FLV, M4V, MP3, or MP4. Alternatively, if they are published through Youtube or Vimeo the encoding step is skipped</p><p>Once uploaded and encoded the administrator can then publish the video.</p>',
        u'This sceencast explains the publish status feature in MediaCore.\nInitially all videos uploaded through the front-end or admin panel are placed under \"awaiting review\" status. Once the administrator hits the \"review complete\" button, they can upload media. Videos can be added in any format, however, they can only be published if they are in a web-ready format such as FLV, M4V, MP3, or MP4. Alternatively, if they are published through Youtube or Vimeo the encoding step is skipped\nOnce uploaded and encoded the administrator can then publish the video.',
        datetime.datetime(2010, 5, 13, 2, 29, 40),
        218,
        u'http://getmediacore.com/files/tutorial-workflow-in-mediacore.mp4',
        u'video',
        u'mp4',
        ),
        (u'creating-a-podcast-in-mediacore',
        u'Creating a Podcast in MediaCore',
        u'<p>This describes the process an administrator goes through in creating a podcast in MediaCore. An administrator can enter information that will automatically generate the iTunes/RSS feed information. Any episodes published to a podcast will automatically publish to iTunes/RSS.</p>',
        u'This describes the process an administrator goes through in creating a podcast in MediaCore. An administrator can enter information that will automatically generate the iTunes/RSS feed information. Any episodes published to a podcast will automatically publish to iTunes/RSS.',
        datetime.datetime(2010, 5, 13, 2, 33, 44),
        100,
        u'http://getmediacore.com/files/tutorial-create-podcast-in-mediacore.mp4',
        u'video',
        u'mp4',
        ),
        (u'adding-a-video-in-mediacore',
        u'Adding a Video in MediaCore',
        u'<p>This screencast shows how video or audio can be added in MediaCore.</p><p>MediaCore supports a wide range of formats including (but not limited to): YouTube, Vimeo, Google Video, Amazon S3, Bits on the Run, BrightCove, Kaltura, and either your own server or someone else\'s.</p><p>Videos can be uploaded in any format, but can only be published in web-ready formats such as FLV, MP3, M4V, MP4 etc.</p>',
        u'This screencast shows how video or audio can be added in MediaCore.\nMediaCore supports a wide range of formats including (but not limited to): YouTube, Vimeo, Google Video, Amazon S3, Bits on the Run, BrightCove, Kaltura, and either your own server or someone else\'s.\nVideos can be uploaded in any format, but can only be published in web-ready formats such as FLV, MP3, M4V, MP4 etc.',
        datetime.datetime(2010, 5, 13, 02, 37, 36),
        169,
        u'http://getmediacore.com/files/tutorial-add-video-in-mediacore.mp4',
        u'video',
        u'mp4',
        ),
    ]

    name = u'MediaCore Team'
    email = u'info@mediacore.com'
    for slug, title, desc, desc_plain, publish_on, duration, url, type_, container in instructional_media:
        media = Media()
        media.author = Author(name, email)
        media.description = desc
        media.description_plain = desc_plain
        media.duration = duration
        media.publish_on = publish_on
        media.slug = slug
        media.title = title
        media.type = type_

        media_file = MediaFile()
        media_file.container = container
        media_file.created_on = publish_on
        media_file.display_name = os.path.basename(url)
        media_file.duration = duration
        media_file.type = type_
        media_file.storage = remote_url_storage
        media_file.unique_id = url

        DBSession.add(media)
        DBSession.add(media_file)

        media.files.append(media_file)
        media.categories.append(category2)

        media.encoded = True
        media.reviewed = True
        media.publishable = True

uikit_colors = {
    'white': {
        'btn_text_color': '#5c5c5e',
        'btn_text_shadow_color': '#fff',
        'btn_text_hover_color': '#4b4b4d',
    },
    'tan': {
        'btn_text_color': '#4a3430',
        'btn_text_shadow_color': '#fff',
        'btn_text_hover_color': '#4a3430',
    },
    'purple': {
        'btn_text_color': '#b0bcc5',
        'btn_text_shadow_color': '#000',
        'btn_text_hover_color': '#fff',
    },
    'blue': {
        'btn_text_color': '#fff',
        'btn_text_shadow_color': '#2d6dd1',
        'btn_text_hover_color': '#ddd',
    },
    'black': {
        'btn_text_color': '#797c7f',
        'btn_text_shadow_color': '#000',
        'btn_text_hover_color': '#ddd',
    },
    'green': {
        'btn_text_color': '#fff',
        'btn_text_shadow_color': '#000',
        'btn_text_hover_color': '#ddd',
    },
    'brown': {
        'btn_text_color': '#fff',
        'btn_text_shadow_color': '#000',
        'btn_text_hover_color': '#ddd',
    },
}

def generate_appearance_css(settings, cache_dir=None):
    """Generate the custom appearance.css file, overwriting if it exists.

    :param settings: A list of settings key-value tuples.
    :param cache_dir: Path to the data directory. Optional if the
        ``pylons.config`` Stacked Object Proxy is available (ie.
        during the life of a request, but not during websetup or init).
    :raises TypeError: If cache_dir is not provided and cannot be found.
    :raises ValueError: If the cache_dir does not exist.

    """
    if cache_dir is None:
        cache_dir = pylons.config['cache.dir']
    if not os.path.exists(cache_dir):
        raise ValueError('No valid cache dir provided.')

    appearance_dir = os.path.join(cache_dir, 'appearance')
    css_path = os.path.join(appearance_dir, 'appearance.css')

    vars = dict((k.encode('utf-8'), v.encode('utf-8'))
                for k, v in settings
                if k.startswith('appearance_'))
    vars['uikit_colors'] = uikit_colors[
        vars['appearance_navigation_bar_color']]
    vars['navbar_color'] = vars['appearance_navigation_bar_color']

    if vars['appearance_logo']:
        logo_path = os.path.join(appearance_dir, vars['appearance_logo'])
        if os.path.exists(logo_path):
            vars['logo_height'] = Image.open(logo_path).size[1]
            vars['logo_name'] = vars['appearance_logo']
        else:
            vars['appearance_logo'] = False

    # Create a simple template loader instead of using
    # mediacore.lib.templating.render because that function only works
    # within the context of a request, when the pylons magic globals
    # have been populated.
    tmpl_loader = TemplateLoader([os.path.join(here, 'templates')])
    tmpl = tmpl_loader.load('appearance.css', cls=NewTextTemplate)
    css = tmpl.generate(**vars).render('text')

    warning = ('/*\n'
               ' * This file is automatically generated by MediaCore.\n'
               ' * Please do not edit this file directly.\n'
               ' */\n\n')

    css_file = open(css_path, 'w')
    css_file.write(warning + css)
    css_file.close()
