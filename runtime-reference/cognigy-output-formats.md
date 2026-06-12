# Cognigy Output Formats

Channel output formats for use in Cognigy Code Nodes with `api.say(text, data)` or `api.output(text, data)`.

All formats use the `_cognigy._default` structure which Cognigy automatically adapts for each channel.

## Text Only

```js
api.say('Hello, how can I help?')
```

## Text with Quick Replies

```js
api.say('What would you like to do?', {
  _cognigy: {
    _default: {
      _quickReplies: {
        type: 'quick_replies',
        text: 'What would you like to do?',
        quickReplies: [
          { contentType: 'postback', payload: 'check_balance', title: 'Check Balance' },
          { contentType: 'postback', payload: 'transfer',      title: 'Transfer Money' },
          { contentType: 'postback', payload: 'help',          title: 'Get Help' }
        ]
      }
    }
  }
})
```

Quick reply `contentType` options: `postback`, `phone_number`, `trigger_intent`.

## Text with Buttons

```js
api.say('Choose an option:', {
  _cognigy: {
    _default: {
      _buttons: {
        type: 'buttons',
        text: 'Choose an option:',
        buttons: [
          { type: 'postback',     payload: 'yes',              title: 'Yes' },
          { type: 'postback',     payload: 'no',               title: 'No' },
          { type: 'web_url',      url: 'https://example.com',  title: 'Learn More' },
          { type: 'phone_number', payload: '+61400000000',      title: 'Call Us' }
        ]
      }
    }
  }
})
```

## Gallery (Carousel)

```js
api.say('', {
  _cognigy: {
    _default: {
      _gallery: {
        type: 'carousel',
        items: [
          {
            title: 'Product One',
            subtitle: 'Great product',
            imageUrl: 'https://example.com/image1.jpg',
            buttons: [
              { type: 'postback', payload: 'buy_one', title: 'Buy Now' }
            ]
          },
          {
            title: 'Product Two',
            subtitle: 'Another great product',
            imageUrl: 'https://example.com/image2.jpg',
            buttons: [
              { type: 'web_url', url: 'https://example.com/two', title: 'View' }
            ]
          }
        ]
      }
    }
  }
})
```

## Image

```js
api.say('', {
  _cognigy: {
    _default: {
      _image: {
        type: 'image',
        imageUrl: 'https://example.com/image.jpg'
      }
    }
  }
})
```

## Audio

```js
api.say('', {
  _cognigy: {
    _default: {
      _audio: {
        type: 'audio',
        audioUrl: 'https://example.com/audio.wav'
      }
    }
  }
})
```

## Video

```js
api.say('', {
  _cognigy: {
    _default: {
      _video: {
        type: 'video',
        videoUrl: 'https://www.youtube.com/watch?v=example'
      }
    }
  }
})
```

## List

```js
api.say('', {
  _cognigy: {
    _default: {
      _list: {
        type: 'list',
        items: [
          {
            title: 'Item One',
            subtitle: 'Description',
            imageUrl: 'https://example.com/img.jpg',
            buttons: [{ type: 'postback', payload: 'select_one', title: 'Select' }]
          }
        ],
        button: { type: 'postback', payload: 'view_all', title: 'View All' }
      }
    }
  }
})
```

## Adaptive Card

```js
api.say('', {
  _cognigy: {
    _default: {
      _adaptiveCard: {
        type: 'adaptiveCard',
        adaptiveCard: {
          type: 'AdaptiveCard',
          version: '1.0',
          body: [
            { type: 'TextBlock', text: 'Hello World', weight: 'bolder', size: 'medium' }
          ],
          actions: [
            { type: 'Action.Submit', title: 'OK', data: { action: 'ok' } }
          ]
        }
      }
    }
  }
})
```
