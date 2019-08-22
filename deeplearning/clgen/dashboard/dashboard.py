"""A flask server which renders test results."""
import threading

import flask
import flask_sqlalchemy
import portpicker
import sqlalchemy as sql

import build_info
from deeplearning.clgen.dashboard import dashboard_db
from labm8 import app
from labm8 import bazelutil
from labm8 import humanize

FLAGS = app.FLAGS

app.DEFINE_integer('clgen_dashboard_port', portpicker.pick_unused_port(),
                   'The port to launch the server on.')

flask_app = flask.Flask(
    __name__,
    template_folder=bazelutil.DataPath(
        'phd/deeplearning/clgen/dashboard/templates'),
    static_folder=bazelutil.DataPath('phd/deeplearning/clgen/dashboard/static'),
)
flask_app.config[
    'SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/phd/deeplearning/clgen/dashboard.db'
db = flask_sqlalchemy.SQLAlchemy(flask_app)


def GetBaseTemplateArgs():
  return {
      'urls': {
          'cache_tag': build_info.BuildTimestamp(),
          'styles_css': flask.url_for('static', filename='bootstrap.css'),
          'site_css': flask.url_for('static', filename='site.css'),
          'site_js': flask.url_for('static', filename='site.js'),
      },
      'build_info': {
          'html': build_info.FormatShortBuildDescription(html=True),
          'version': build_info.Version(),
      },
      'dashboard_info': {
          'db': flask_app.config['SQLALCHEMY_DATABASE_URI'],
      }
  }


@flask_app.route('/')
def index():
  corpuses = db.session.query(dashboard_db.Corpus.id,
                              dashboard_db.Corpus.encoded_url,
                              dashboard_db.Corpus.summary).all()
  models = db.session.query(
      dashboard_db.Model.id, dashboard_db.Model.cache_path,
      dashboard_db.Model.corpus_id, dashboard_db.Model.summary).all()

  data = {
      'corpuses': {
          x.id: {
              'name': x.encoded_url,
              'summary': x.summary,
              'models': {}
          } for x in corpuses
      },
  }

  for model in sorted(models, key=lambda x: x.id):
    data['corpuses'][model.corpus_id]['models'][model.id] = {
        'name': model.cache_path,
        'summary': model.summary,
    }

  return flask.render_template('dashboard.html',
                               data=data,
                               **GetBaseTemplateArgs())


@flask_app.route('/corpus/<int:corpus_id>/model/<int:model_id>/')
def report(corpus_id: int, model_id: int):
  corpus = db.session.query(dashboard_db.Corpus.summary)\
      .filter(dashboard_db.Corpus.id == corpus_id).one()
  model = db.session.query(dashboard_db.Model.summary)\
      .filter(dashboard_db.Model.id == model_id).one()

  telemetry = db.session.query(dashboard_db.TrainingTelemetry.timestamp,
                               dashboard_db.TrainingTelemetry.epoch,
                               dashboard_db.TrainingTelemetry.step,
                               dashboard_db.TrainingTelemetry.training_loss)\
      .filter(dashboard_db.TrainingTelemetry.model_id == model_id).all()

  q1 = db.session.query(sql.func.max(dashboard_db.TrainingTelemetry.id))\
      .filter(dashboard_db.TrainingTelemetry.model_id == model_id)\
      .group_by(dashboard_db.TrainingTelemetry.epoch)

  q2 = db.session.query(
    dashboard_db.TrainingTelemetry.timestamp,
    dashboard_db.TrainingTelemetry.epoch,
    dashboard_db.TrainingTelemetry.step,
    dashboard_db.TrainingTelemetry.learning_rate,
    dashboard_db.TrainingTelemetry.training_loss,
    dashboard_db.TrainingTelemetry.pending)\
    .filter(dashboard_db.TrainingTelemetry.id.in_(q1))\
    .order_by(dashboard_db.TrainingTelemetry.id)

  q3 = db.session.query(
        sql.sql.expression.cast(sql.func.avg(dashboard_db.TrainingTelemetry.ns_per_batch), sql.Integer).label('us_per_step'),
      ).group_by(dashboard_db.TrainingTelemetry.epoch)\
       .filter(dashboard_db.TrainingTelemetry.model_id == model_id)\
       .order_by(dashboard_db.TrainingTelemetry.id)

  epoch_telemetry = [{
      'timestamp': r2.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
      'epoch': r2.epoch,
      'step': humanize.Commas(r2.step),
      'learning_rate': f'{r2.learning_rate:.5E}',
      'training_loss': f'{r2.training_loss:.6f}',
      'pending': r2.pending,
      'us_per_step': humanize.Duration(r3.us_per_step / 1e6),
  } for r2, r3 in zip(q2, q3)]

  data = {
      'telemetry': telemetry,
      'epoch_telemetry': epoch_telemetry,
  }

  return flask.render_template('report.html',
                               data=data,
                               corpus_id=corpus_id,
                               model_id=model_id,
                               corpus=corpus,
                               model=model,
                               **GetBaseTemplateArgs())


@flask_app.route(
    '/corpus/<int:corpus_id>/model/<int:model_id>/samples/<int:epoch>')
def samples(corpus_id: int, model_id: int, epoch: int):
  samples = db.session.query(dashboard_db.TrainingSample.sample,
                             dashboard_db.TrainingSample.token_count,
                             dashboard_db.TrainingSample.sample_time)\
      .filter(dashboard_db.TrainingSample.model_id == model_id,
              dashboard_db.TrainingSample.epoch == epoch).all()

  data = {
      'samples': samples,
  }

  opts = GetBaseTemplateArgs()
  opts['urls']['back'] = f'/corpus/{corpus_id}/model/{model_id}/'

  return flask.render_template('samples.html',
                               data=data,
                               corpus_id=corpus_id,
                               model_id=model_id,
                               **opts)


def Launch(debug: bool = False):
  """Launch dashboard in a separate thread."""
  app.Log(1, 'Launching dashboard on http://127.0.0.1:%d',
          FLAGS.clgen_dashboard_port)
  kwargs = {
      'port': FLAGS.clgen_dashboard_port,
      # Debugging must be disabled when run in a separate thread.
      'debug': debug,
      'host': '0.0.0.0',
  }
  db.create_all()
  if debug:
    flask_app.run(**kwargs)
  else:
    thread = threading.Thread(target=flask_app.run, kwargs=kwargs)
    thread.setDaemon(True)
    thread.start()
    return thread