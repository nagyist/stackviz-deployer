module.exports = {
	basePath: __dirname,
	publicFolder: 'public',
	proxy: {
		'/api': 'http://localhost:5000'
	},
	port: 5001,
	livereload: true,
	enableJava: false,
};
