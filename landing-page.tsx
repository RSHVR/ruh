import React from 'react';
import { ArrowRight, Chrome } from 'lucide-react';

const LandingPage = () => {
  const tutorialSteps = [
    {
      title: "Install the Extension",
      description: "Add our extension to Chrome with just one click and start saving immediately.",
      image: "/api/placeholder/800/600"
    },
    {
      title: "Browse Normally",
      description: "Continue shopping on your favorite sites. We'll automatically detect when savings are available.",
      image: "/api/placeholder/800/600"
    },
    {
      title: "Save Instantly",
      description: "When we find a better deal, just click to apply the savings to your purchase.",
      image: "/api/placeholder/800/600"
    }
  ];

  const beforeAfterImages = [
    {
      before: "/api/placeholder/400/600",
      after: "/api/placeholder/400/600",
      title: "Sarah saved $150"
    },
    {
      before: "/api/placeholder/400/600",
      after: "/api/placeholder/400/600",
      title: "Mike saved $200"
    },
    {
      before: "/api/placeholder/400/600",
      after: "/api/placeholder/400/600",
      title: "Lisa saved $175"
    }
  ];

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Section */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-6">
            Save Money Automatically While You Shop
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Our browser extension finds the best deals so you don't have to
          </p>
          <a
            href="#"
            className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition"
          >
            <Chrome className="mr-2" />
            Add to Chrome - It's Free
          </a>
        </div>
      </section>

      {/* Tutorial Section */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            How It Works
          </h2>
          <div className="space-y-16">
            {tutorialSteps.map((step, index) => (
              <div key={index} className="flex items-center gap-8">
                <div className="w-2/3">
                  <img
                    src={step.image}
                    alt={`Step ${index + 1}`}
                    className="rounded-lg shadow-lg w-full"
                  />
                </div>
                <div className="w-1/3">
                  <h3 className="text-2xl font-semibold text-gray-900 mb-4">
                    {step.title}
                  </h3>
                  <p className="text-gray-600">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Before/After Section */}
      <section className="py-16">
        <div className="max-w-6xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            Real People, Real Savings
          </h2>
          <div className="relative">
            <div className="flex overflow-x-auto space-x-8 pb-8 snap-x">
              {beforeAfterImages.map((item, index) => (
                <div
                  key={index}
                  className="flex-none w-[800px] snap-center"
                >
                  <div className="flex gap-4">
                    <div className="relative">
                      <img
                        src={item.before}
                        alt="Before"
                        className="rounded-lg"
                      />
                      <span className="absolute top-4 left-4 bg-white px-4 py-2 rounded-full font-semibold">
                        Before
                      </span>
                    </div>
                    <div className="relative">
                      <img
                        src={item.after}
                        alt="After"
                        className="rounded-lg"
                      />
                      <span className="absolute top-4 left-4 bg-white px-4 py-2 rounded-full font-semibold">
                        After
                      </span>
                    </div>
                  </div>
                  <p className="text-center text-xl font-semibold mt-4">
                    {item.title}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;