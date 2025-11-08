"""
Simple local web server to handle OAuth callbacks for TikTok
Used during authentication flow
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
import threading


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback requests"""

    auth_code = None

    def do_GET(self):
        """Handle GET request from OAuth redirect"""
        # Parse the URL
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/callback':
            # Extract authorization code
            params = parse_qs(parsed_path.query)

            if 'code' in params:
                OAuthCallbackHandler.auth_code = params['code'][0]

                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authorization Successful</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            min-height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        }
                        .container {
                            background: white;
                            padding: 3rem;
                            border-radius: 1rem;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                            text-align: center;
                        }
                        h1 { color: #333; margin-bottom: 1rem; }
                        p { color: #666; font-size: 1.1rem; }
                        .success { color: #10b981; font-size: 3rem; margin-bottom: 1rem; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="success">✓</div>
                        <h1>Authorization Successful!</h1>
                        <p>You can close this window and return to the application.</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
            else:
                # Error in authorization
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()

                error_msg = params.get('error_description', ['Unknown error'])[0]
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authorization Failed</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            min-height: 100vh;
                            margin: 0;
                            background: #fee;
                        }}
                        .container {{
                            background: white;
                            padding: 3rem;
                            border-radius: 1rem;
                            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                            text-align: center;
                        }}
                        h1 {{ color: #dc2626; }}
                        p {{ color: #666; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Authorization Failed</h1>
                        <p>{error_msg}</p>
                    </div>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


def start_oauth_server(port=8000, timeout=300):
    """
    Start a local OAuth callback server

    Args:
        port: Port to listen on
        timeout: How long to wait for callback (seconds)

    Returns:
        Authorization code or None
    """
    server_address = ('', port)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)

    print(f"Starting OAuth callback server on http://localhost:{port}")
    print("Waiting for authorization...")

    # Run server in a thread with timeout
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # Wait for auth code with timeout
    import time
    start_time = time.time()
    while OAuthCallbackHandler.auth_code is None:
        if time.time() - start_time > timeout:
            print("\nTimeout waiting for authorization")
            httpd.shutdown()
            return None
        time.sleep(0.5)

    # Give browser time to display success page
    time.sleep(2)
    httpd.shutdown()

    return OAuthCallbackHandler.auth_code


if __name__ == '__main__':
    # Test the server
    code = start_oauth_server()
    print(f"Received authorization code: {code}")
