import json

from flask import Flask, send_file, request, Response
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app, supports_credentials=True)


@app.route("/")
def root():
    return send_file("static/index.html")


# Whenever a request matches the given URL, the function is triggered.
# The method specifies the type of requests to which this route should respond (e.g. POST only).
# Request types:
#   GET is used to request data from a specified source.
#   POST is used to send data to a server to create/update a resource.
#   PUT is used to update a current resource with new data.
#   DELETE is used to delete a specific resource.
# In the case below, we are sending data from the frontend to the backend.
@app.route("/example", methods=["POST"])
def receiveExample() -> Response:
    _json = request.get_json()
    print(f"Received: {_json}")
    return Response(status=200)


@app.route("/example", methods=["GET"])
def sendExample(template_name: str = "2x2k") -> Response:
    template_name = request.args.get("template_name", template_name)
    file_path = "./web/template_" + template_name + ".json"
    with open(file_path) as file:
        _json = json.load(file)
    print(f"Sending: {_json}")
    return Response(json.dumps(_json), status=200)


if __name__ == "__main__":
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host="127.0.0.1", port=5000, debug=True)


@app.route("/stim", methods=["POST"])
@cross_origin(supports_credentials=True)
def jsonToStim() -> Response:
    _json = request.get_json()
    filename = "circuit.stim"
    with open(filename, "w") as f:
        json.dump(_json, f)
    return send_file(filename)
