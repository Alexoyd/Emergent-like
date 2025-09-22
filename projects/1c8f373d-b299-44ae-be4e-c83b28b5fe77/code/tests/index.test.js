const request = require('supertest');
const app = require('../src/index');

describe('GET /', () => {
  it('should return Hello World message', async () => {
    const response = await request(app).get('/');
    expect(response.status).toBe(200);
    expect(response.body.message).toContain('Hello World');
  });
});
